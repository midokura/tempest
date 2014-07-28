__author__ = 'Albert'

import collections

from tempest.api.network import common as net_common
from tempest.common.utils.data_utils import rand_name
from tempest.openstack.common import log as logging
from tempest.scenario import manager
from neutronclient.common import exceptions as exc
from pprint import pprint
from tempest import test


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
        cfg = cls.config.network
        if not (cfg.tenant_networks_reachable or cfg.public_network_id):
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
        #Is this no longer required?
        """
        cls.keypairs = {}
        cls.security_groups = {}
        cls.networks = []
        cls.subnets = []
        cls.routers = []
        cls.servers = []
        cls.floating_ips = {}
        cls.admin = TenantAdmin()
        """

    def basic_scenario(self):
        self._create_keypairs()
        self._create_security_groups()
        self._create_networks()
        self._check_networks()
        self._create_servers()
        self._assign_floating_ips()

    def custom_scenario(self, scenario):
        tenant_id = None
        pprint("######")
        for tenant in scenario['tenants']:
            if tenant['type'] == 'default':
                tenant_id = self.tenant_id
            else:
                tenant_id = self._create_tenant()
            """
            self._create_custom_keypairs(tenant_id)
            self._create_custom_security_groups(tenant_id)
            """
            for network in tenant['networks']:
                network['tenant_id'] = tenant_id
                self.network, self.mysubnets, myrouter = \
                    self._create_custom_networks(network)
                self._check_networks()
                self.servers = {}
                for server in network['servers']:
                    name = rand_name('server-smoke-')
                    myserver = self._create_server(name, self.network)
                    self.servers.append(myserver)
                    pprint(server['floating_ip'])
                    if server['floating_ip']:
                        self._assign_custom_floating_ips(myserver)

    def _create_tenant(self):
        # Create a tenant that is enabled
        tenant = self.admin.tenant_create_enabled()
        tenant_id = tenant['id']
        return tenant_id

    def _create_custom_keypairs(self, tenant_id):
        self.keypairs[tenant_id] = self.create_keypair(
            name=rand_name('keypair-smoke-'))

    def _create_custom_security_groups(self, tenant_id):
        self.security_groups[tenant_id] = self._create_security_group()

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
        """
        self.networks.append(network)
        self.subnets.append(subnet)
        if router:
            self.routers.append(router)
        """
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

    def _create_custom_subnet(self, network, mysubnet, namestart='subnet-smoke-'):
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
        self.set_resource(rand_name(namestart), subnet)
        return subnet

    def _create_server(self, name, network):
        pprint("server creation")
        pprint(network['tenant_id'])
        tenant_id = network['tenant_id']
        keypair_name = self.keypairs[tenant_id].name
        pprint(keypair_name)
        pprint(self.security_groups[tenant_id])
        security_groups = [self.security_groups[tenant_id].name]
        pprint("security groups")
        pprint(security_groups)
        create_kwargs = {
            'nics': [
                {'net-id': network['id']},
                ],
            'key_name': keypair_name,
            'security_groups': security_groups,
            }
        pprint(create_kwargs)
        server = self.create_server(name=name, create_kwargs=create_kwargs)
        return server

    def _create_servers(self):
        pprint(self.networks)
        for i, network in enumerate(self.networks):
            name = rand_name('server-smoke-%d-' % i)
            server = self._create_server(name, network)
            self.servers.append(server)
            return server

    def _assign_floating_ips(self):
        public_network_id = self.config.network.public_network_id
        for server in self.servers:
            floating_ip = self._create_floating_ip(server, public_network_id)
            self.floating_ips.setdefault(server, [])
            self.floating_ips[server].append(floating_ip)

    def _assign_custom_floating_ips(self, server):
        pprint("assign floating ip")
        pprint(server)
        public_network_id = self.config.network.public_network_id
        floating_ip = self._create_floating_ip(server, public_network_id)
        self.floating_ips.setdefault(server, [])
        self.floating_ips[server].append(floating_ip)