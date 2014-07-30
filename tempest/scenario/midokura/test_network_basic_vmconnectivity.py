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
from tempest.scenario import manager
from tempest.test import services
from tempest import test

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
        tenant = self.tenants[self.tenant_id]
        access_point_ssh = self._connect_to_access_point(tenant)
        for server in self.servers:
            if server.id != tenant.access_point.id:
                dest = self._get_server_ip(server)
                self._check_connectivity(access_point=access_point_ssh,
                                         ip=dest)
                access_point_ssh.ping_host(dest)

    def _check_connectivity(self, access_point, ip, should_succeed=True):
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
        self._check_connectivity()
