__author__ = 'Albert'
'''
Scenario:
A launched VM should get an ip address and routing table entries from DHCP. And
it should be able to metadata service.

Pre-requisites:
1 tenant
1 network
1 VM

Steps:
1. create a network
2. launch a VM
3. verify that the VM gets IP address
4. verify that the VM gets default GW in the routing table
5. verify that the VM gets a routing entry for metadata service via dhcp agent

Expected results:
vm should get an ip address (confirm by "ip addr" command) 
VM should get a defaut gw
VM should get a route for 169.254.169.254 (on non-cirros )

'''


from tempest.common import debug
from tempest import config
from tempest.openstack.common import log as logging
from tempest.scenario.midokura.midotools import scenario
from tempest.test import services
from tempest import test
from time import sleep
from pprint import pprint

CONF = config.CONF
LOG = logging.getLogger(__name__)
CIDR1 = "10.10.1.0/24"

class TestNetworkBasicVMConnectivity(scenario.TestScenario):

    @classmethod
    def setUpClass(cls):
        super(TestNetworkBasicVMConnectivity, cls).setUpClass()
        cls.check_preconditions()

    def setUp(self):
        super(TestNetworkBasicVMConnectivity, self).setUp()
        self.security_group = \
            self._create_security_group_neutron(tenant_id=self.tenant_id)
        self._scenario_conf()
        self.custom_scenario(self.scenario)

    def _scenario_conf(self):
        serverB = {
            'floating_ip': False,
        }
        subnetA = {
            "network_id": None,
            "ip_version": 4,
            "cidr": CIDR1,
            "allocation_pools": None
        }
        networkA = {
            'subnets': [subnetA],
            'servers': [serverB],
        }
        tenantA = {
            'networks': [networkA],
            'tenant_id': None,
            'type': 'default',
            'hasgateway': True
        }
        self.scenario = {
            'tenants': [tenantA],
        }

    def _check_ip(self):

        ap_details = self.access_point.keys()[0]
        networks = ap_details.networks
        for server in self.servers:
            #servers should only have 1 network
            name = server.networks.keys()[0]
            if any(i in networks.keys() for i in server.networks.keys()):
                remote_ip = server.networks[name][0]
                pk = self.servers[server].private_key
                self._serious_test(remote_ip, pk)
                return True
            else:
                LOG.info("FAIL - No ip connectivity to the server ip: %s" % server.networks[name][0])
            raise Exception("FAIL - No ip for this network : %s"
                            % server.networks)

    def _serious_test(self, remote_ip, pk):
        #access_point_ssh = self.connect_to_access_point(self.access_point)
        LOG.info("Trying to get the list of ips")
        try:
            ssh_client = self.setup_tunnel(remote_ip, pk)
            result = ssh_client.get_ip_list()
            pprint(result)
        except Exception as inst:
            LOG.info(inst.args)
            LOG.info
            #debug.log_ip_ns()
            raise

    def _check_connectivity(self, access_point, ip, should_succeed=True):
        LOG.info("checking connectivity to ip: %s " % ip)
        if should_succeed:
            msg = "Timed out waiting for %s to become reachable" % ip
        else:
            msg = "%s is reachable" % ip
        try:
            self.assertTrue(self._check_remote_connectivity(access_point, ip,
                                                            should_succeed),
                            msg)
        except test.exceptions.SSHTimeout:
            raise
        except Exception:
            debug.log_net_debug()
            raise

    @services('compute', 'network')
    def test_network_basic_vmconnectivity(self):
        self.assertTrue(self._check_ip())

