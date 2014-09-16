#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
__author__ = 'Albert'
__email__ = "albert.vico@midokura.com"

from tempest import config
from tempest.openstack.common import log as logging
from tempest.scenario.midokura.midotools import scenario
from tempest import test

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
            "allocation_pools": None,
            "routers": None,
            "dns": [],
            "routes": [],
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
            self.network_client.update_router(
                router.id, {'router': {'admin_state_up': False}})
            LOG.info("router test")
            self.check_public_network_connectivity(False)
            self.network_client.update_router(
                router.id, {'router': {'admin_state_up': True}})

    def _check_vm_connectivity_net(self):
        for network in self.networks:
            LOG.info("network test")
            self.network_client.update_network(
                network.id, {'network': {'admin_state_up': False}})
            self.check_public_network_connectivity(False)
            self.network_client.update_network(
                network.id, {'network': {'admin_state_up': True}})

    def _check_vm_connectivity_port(self):
        LOG.info("port test")
        floating_ip, server = self.floating_ip_tuple
        port_id = floating_ip.get("port_id")
        self.network_client.update_port(
            port_id, {'port': {'admin_state_up': False}})
        self.check_public_network_connectivity(False)
        self.network_client.update_port(
            port_id, {'port': {'admin_state_up': True}})

    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_adminstateup(self):
        LOG.info("Starting Router test")
        self._check_vm_connectivity_router()
        self.check_public_network_connectivity(True)
        LOG.info("End of Rotuer test")
        LOG.info("Starting Network test")
        self._check_vm_connectivity_net()
        self.check_public_network_connectivity(True)
        LOG.info("End of Net test")
        LOG.info("Starting Port test")
        self._check_vm_connectivity_port()
        LOG.info("End of Port test")
        self.check_public_network_connectivity(True)