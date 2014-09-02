__author__ = 'Albert'
__email__ = "albert.vico@midokura.com"

import collections

from tempest.api.network import common as net_common
from tempest.common.utils.data_utils import rand_name
from tempest.openstack.common import log as logging
from tempest.scenario import manager
from tempest import config
from neutronclient.common import exceptions as exc
from tempest import test
from tempest.common.utils.linux import remote_client
from tempest.scenario.midokura.midotools.admintools import TenantAdmin



CONF = config.CONF
LOG = logging.getLogger(__name__)

'''
This needs a heavy refactor since it is mainly though and designed to work with a single tenant
'''

Floating_IP_tuple = collections.namedtuple('Floating_IP_tuple',
                                           ['floating_ip', 'server'])


class TestScenario(manager.NetworkScenarioTest):


    @classmethod
    def check_preconditions(cls):
        super(TestScenario, cls).check_preconditions()
        if not (CONF.network.tenant_networks_reachable
                or CONF.network.public_network_id):
            msg = ('Either tenant_networks_reachable must be "true", or '
                   'public_network_id must be defined.')
            cls.enabled = False
            raise cls.skipException(msg)

    @classmethod
    def setUpClass(cls):
        # Create no network resources for these tests.
        cls.set_network_resources()
        super(TestScenario, cls).setUpClass()
        for ext in ['router', 'security-group']:
            if not test.is_extension_enabled(ext, 'network'):
                msg = "%s extension not enabled." % ext
                raise cls.skipException(msg)
        cls.check_preconditions()
        cls.admin = TenantAdmin()
        cls.tenants = {}

    def setUp(self):
        super(TestScenario, self).setUp()
        self.cleanup_waits = []
        self.addCleanup(self._wait_for_cleanups)
        self.networks = []
        self.subnets = []
        self.routers = []
        self.floating_ips = {}
        self.masterkey = None

    def custom_scenario(self, scenario):
        tenant_id = None
        for tenant in scenario['tenants']:
            if tenant['type'] == 'default':
                tenant_id = self.tenant_id
                self.tenants[tenant_id] = self.admin.get_tenant(tenant_id)
            else:
                tenant_id = self._create_tenant()
            if tenant['MasterKey']:
                self._create_custom_keypairs(tenant_id)

            for network in tenant['networks']:
                network['tenant_id'] = tenant_id
                cnetwork, subnets, router = \
                    self._create_custom_networks(network)
                self.networks.append(cnetwork)
                self.subnets.extend(subnets)
                if router:
                    self.routers.append(router)
                self._check_networks()
                self.servers = {}
                for server in network['servers']:
                    name = rand_name('server-smoke-')
                    serv_dict = self._create_server(name, cnetwork,)
                    self.servers[serv_dict['server']] = serv_dict['keypair']
                    if server['floating_ip']:
                        self._assign_custom_floating_ips(serv_dict['server'])
            if tenant['hasgateway']:
                self._build_gateway(self.tenants[tenant_id])

    def check_public_network_connectivity(self, should_connect=True,
                                           msg=None):
        ssh_login = CONF.compute.image_ssh_user
        floating_ip, server = self.floating_ip_tuple
        ip_address = floating_ip.floating_ip_address
        private_key = None
        if should_connect:
            private_key = self.servers[server].private_key
        # call the common method in the parent class
        super(TestScenario, self)._check_public_network_connectivity(
            ip_address, ssh_login, private_key, should_connect, msg,
            self.servers.keys())

    #does not work for non floating ips, needs refactor
    def get_server_ip(self, server=None, isgateway=False, floating=False):
        """
        returns the ip (floating/internal) of a server
        """
        if floating:
            server_ip = self.floating_ips[server].floating_ip_address
        else:
            server_ip = None
            if isgateway:
                network_name = self.gw_network['name']
                server = self.access_point.keys()[0]
            else:
                network_name = self.tenants[server.tenant_id].network.name
            if network_name in server.networks:
                server_ip = server.networks[network_name][0]
        return server_ip

    def _create_tenant(self):
        # Create a tenant that is enabled
        tenant = self.admin.tenant_create_enabled()
        tenant_id = tenant['id']
        self.tenants[tenant_id] = tenant
        return tenant_id

    def _create_custom_keypairs(self, tenant_id):
        self.masterkey = self.create_keypair(
            name="masterkey")

    def _create_custom_networks(self, mynetwork):
        network = self._create_network(mynetwork['tenant_id'])
        router = None
        subnets = []
        if mynetwork.get('router'):
            router = self._get_router(mynetwork['tenant_id'])
        for mysubnet in mynetwork['subnets']:
            subnet = self._create_custom_subnet(network, mysubnet)
            subnets.append(subnet)
            if router:
                subnet.add_to_router(router.id)
        return network, subnets, router

    def _check_networks(self):
        # Checks that we see the newly created network/subnet/router via
        # checking the result of list_[networks,routers,subnets]
        seen_nets = self._list_networks()
        seen_names = [n['name'] for n in seen_nets]
        seen_ids = [n['id'] for n in seen_nets]
        for mynet in self.networks:
            self.assertIn(mynet.name, seen_names)
            self.assertIn(mynet.id, seen_ids)

        seen_subnets = self._list_subnets()
        seen_net_ids = [n['network_id'] for n in seen_subnets]
        seen_subnet_ids = [n['id'] for n in seen_subnets]
        for mynet in self.networks:
            self.assertIn(mynet.id, seen_net_ids)
        for mysubnet in self.subnets:
            self.assertIn(mysubnet.id, seen_subnet_ids)
        seen_routers = self._list_routers()
        seen_router_ids = [n['id'] for n in seen_routers]
        seen_router_names = [n['name'] for n in seen_routers]
        for myrouter in self.routers:
            self.assertIn(myrouter.name, seen_router_names)
            self.assertIn(myrouter.id, seen_router_ids)

    def _create_custom_subnet(self, network, mysubnet):
        """
        Create a subnet for the given network with the cidr given.
        """
        result = None
        body = dict(
            subnet=dict(
                ip_version=4,
                network_id=network.id,
                tenant_id=network.tenant_id,
                cidr=str(mysubnet["cidr"]),
            ),
        )
        #body['subnet'].update(kwargs)
        try:
            result = self.network_client.create_subnet(body=body)
        except exc.NeutronClientException as e:
            is_overlapping_cidr = 'overlaps with another subnet' in str(e)
            if not is_overlapping_cidr:
                raise
        self.assertIsNotNone(result, 'Unable to allocate tenant network')
        subnet = net_common.DeletableSubnet(client=self.network_client,
                                            **result['subnet'])
        self.assertEqual(subnet.cidr, str(mysubnet['cidr']))
        self.addCleanup(self.delete_wrapper, subnet)
        return subnet

    def _create_server(self, name, network, security_groups=None, isgateway=None):
        if not self.masterkey:
            keypair = self.create_keypair(name='keypair-%s' % name)
        else:
            keypair = self.masterkey

        if security_groups is None:
            security_groups = [self.security_group.name]
        nics = [{'net-id': network.id}, ]
        if isgateway:
            for network in self.networks:
                nics.append({'net-id': network.id})
        create_kwargs = {
            'nics': nics,
            'key_name': keypair.name,
            'security_groups': security_groups,
        }
        server = self.create_server(name=name, create_kwargs=create_kwargs)
        return dict(server=server, keypair=keypair)

    def _create_servers(self):
        for i, network in enumerate(self.networks):
            name = rand_name('server-smoke-%d-' % i)
            server = self._create_server(name, network)
            self.servers.append(server)
            return server

    def _create_and_associate_floating_ips(self):
        public_network_id = CONF.network.public_network_id
        for server in self.servers.keys():
            floating_ip = self._create_floating_ip(server, public_network_id)
            self.floating_ip_tuple = Floating_IP_tuple(floating_ip, server)

    def _assign_custom_floating_ips(self, server):
        LOG.info("assign floating ip")
        public_network_id = CONF.network.public_network_id
        floating_ip = self._create_floating_ip(server, public_network_id)
        self.floating_ip_tuple = Floating_IP_tuple(floating_ip, server)

    def _get_custom_server_port_id(self, server, ip_addr=None):
        ports = self._list_ports(device_id=server.id)
        #pprint(ports)
        if ip_addr:
            for port in ports:
                if port['fixed_ips'][0]['ip_address'] == ip_addr:
                    return port['id']
            #ports = [p for p in ports['ports'] if p['fixed_ips'][0]['ip_address'] == ip_addr]
        self.assertEqual(len(ports), 1,
                         "Unable to determine which port to target.")
        return ports[0]['id']

    """
    GateWay methods
    """
    def _build_gateway(self, tenant):
        network, subnet, router = self._create_networks(tenant['id'])
        self.gw_network = network
        self.gw_subnet = subnet
        self.gw_router = router
        self.access_point = {}
        self._set_access_point(tenant, network)

    def _set_access_point(self, tenant, network):
        """
        creates a server in a secgroup with rule allowing external ssh
        in order to access tenant internal network
        workaround ip namespace
        """
        name = 'server-{tenant}-access_point-'.format(
            tenant=tenant['name'])
        name = rand_name(name)
        serv_dict = self._create_server(name, network, isgateway=True)
        self.access_point[serv_dict['server']] = serv_dict['keypair']
        self._assign_access_point_floating_ip(serv_dict['server'])
        self._fix_access_point(self.access_point)

    def _assign_access_point_floating_ip(self, server):
        public_network_id = CONF.network.public_network_id
        server_ip = self.get_server_ip(isgateway=True)
        port_id = self._get_custom_server_port_id(server, ip_addr=server_ip)
        floating_ip = self._create_floating_ip(server, public_network_id, port_id)
        self.floating_ips.setdefault(server, floating_ip)
        self.floating_ip_tuple = Floating_IP_tuple(floating_ip, server)

    def _fix_access_point(self, access_point):
        """
        Hotfix for cirros images
        """
        server, keypair = access_point.items()[0]
        access_point_ip = \
            self.floating_ips[server].floating_ip_address
        private_key = keypair.private_key

        #should implement a wait for status "ACTIVE" function
        access_point_ssh = self._ssh_to_server(access_point_ip,
                                               private_key=private_key)
        #fix for cirros image in order to enable a second eth
        if access_point_ssh.exec_command("cat /sys/class/net/eth1/operstate") is not "up\n":
            try:
                result = access_point_ssh.exec_command("sudo /sbin/udhcpc -i eth1", 60)
                LOG.info(result)
            except:
                pass

    def setup_tunnel(self, tunnel_hops):
        if self.access_point:
            server, keypair = self.access_point.items()[0]
            gw_pkey = keypair.private_key
            fip = self.get_server_ip(server, floating=True)

            GWS = []
            gw = {
            "username": "cirros",
             "ip": fip,
             "password": "cubswin:)",
             "pkey": gw_pkey,
             "key_filename": None
            }
            GWS.append(gw)

            #last element is the final destination
            for host in tunnel_hops[:-1]:
                gw_host = {
                    "username":"cirros",
                    "ip":host[0],
                    "password":"cubswin:)",
                    "pkey":host[1],
                    "key_filename": None
                }
                GWS.append(gw_host)


            ssh_client =remote_client.RemoteClient(
                server=tunnel_hops[-1][0], username='cirros', password='cubswin:)',
                pkey=tunnel_hops[-1][1], gws=GWS
            )
            return ssh_client


