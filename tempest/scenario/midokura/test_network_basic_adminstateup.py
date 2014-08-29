__author__ = 'Albert'
__email__ = "albert.vico@midokura.com"
# vim: tabstop=4 shiftwidth=4 softtabstop=4

from tempest import config
from tempest.openstack.common import log as logging
from tempest.scenario.midokura.midotools import scenario
from tempest.test import attr
from tempest.test import services
from pprint import pprint

CONF = config.CONF
LOG = logging.getLogger(__name__)
CIDR1 = "10.10.1.0/24"

class TestAdminStateUp(scenario.TestScenario):

    @classmethod
    def setUpClass(cls):
        super(TestAdminStateUp, cls).setUpClass()
        cls.scenario = {}

    def setUp(self):
        super(TestAdminStateUp, self).setUp()
        self.security_group = \
            self._create_security_group_neutron(tenant_id=self.tenant_id)
        self._scenario_conf()
        self.custom_scenario(self.scenario)

    def _scenario_conf(self):
        serverA = {
            'floating_ip': True
        }
        subnetA = {
            "network_id": None,
            "ip_version": 4,
            "cidr": CIDR1,
            "allocation_pools": None
        }
        networkA = {
            'subnets': [subnetA],
            'servers': [serverA],
            'router': True
        }
        tenantA = {
            'networks': [networkA],
            'tenant_id': None,
            'type': 'default',
            'hasgateway': False,
            'MasterKey': False,
        }
        self.scenario = {
            'tenants': [tenantA],
        }

    def _check_vm_connectivity_router(self):
        for router in self.routers:
            self.network_client.update_router(router.id, {'router': {'admin_state_up': False}})
            pprint("router test")
            self.check_public_network_connectivity(False)
            self.network_client.update_router(router.id, {'router': {'admin_state_up': True}})

    def _check_vm_connectivity_net(self):
        for network in self.networks:
            pprint("network test")
            self.network_client.update_network(network.id, {'network': {'admin_state_up': False}})
            self.check_public_network_connectivity(False)
            self.network_client.update_network(network.id, {'network': {'admin_state_up': True}})

    def _check_vm_connectivity_port(self):
        pprint("port test")
        floating_ip, server = self.floating_ip_tuple
        port_id = floating_ip.get("port_id")
        self.network_client.update_port(port_id, {'port': {'admin_state_up': False}})
        self.check_public_network_connectivity(False)
        self.network_client.update_port(port_id, {'port': {'admin_state_up': True}})


    @attr(type='smoke')
    @services('compute', 'network')
    def test_network_adminstateup(self):
        LOG.info("Starting Router test")
        self._check_vm_connectivity_router()
        self.check_public_network_connectivity(True)
        pprint("End of Rotuer test")
        LOG.info("Starting Network test")
        self._check_vm_connectivity_net()
        self.check_public_network_connectivity(True)
        pprint("End of Net test")
        LOG.info("Starting Port test")
        self._check_vm_connectivity_port()
        pprint("End of Port test")
        self.check_public_network_connectivity(True)


