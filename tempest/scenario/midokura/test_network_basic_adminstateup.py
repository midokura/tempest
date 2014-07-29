__author__ = 'Albert'
__email__ = "albert.vico@midokura.com"
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack Foundation
# Copyright 2013 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.
#
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

from tempest.api.network import common as net_common
from tempest.common import debug
from tempest.common.utils.data_utils import rand_name
from tempest import config
from tempest.openstack.common import log as logging
from tempest.scenario import manager
from tempest.test import attr
from tempest.test import services
from pprint import pprint

CONF = config.CONF
LOG = logging.getLogger(__name__)
CIDR1 = "10.10.1.0/24"

class TestAdminStateUp(manager.NetworkScenarioTest):

    CONF = config.TempestConfig()

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
            'type': 'default'
        }
        self.scenario = {
            'tenants': [tenantA],
        }

    def _do_test_vm_connectivity_admin_state_up(self):
        must_fail = False
        try:
            self._check_public_network_connectivity()
        except Exception as exc:
            must_fail = True
            LOG.exception(exc)
            debug.log_ip_ns()
        finally:
            self.assertEqual(must_fail, True, "No connection to VM")

    def _check_vm_connectivity_router(self):
        for router in self.routers:
            self.network_client.update_router(router.id, {'router': {'admin_state_up': False}})
            pprint("router test")
            self._do_test_vm_connectivity_admin_state_up()
            self.network_client.update_router(router.id, {'router': {'admin_state_up': True}})

    def _check_vm_connectivity_net(self):
        for network in self.networks:
            pprint("network test")
            self.network_client.update_network(network.id, {'network': {'admin_state_up': False}})
            self._do_test_vm_connectivity_admin_state_up()
            self.network_client.update_network(network.id, {'network': {'admin_state_up': True}})

    def _check_vm_connectivity_port(self):
        pprint("port test")
        for server, floating_ips in self.floating_ips.iteritems():
            for floating_ip in floating_ips:
                port_id = floating_ip.get("port_id")
                self.network_client.update_port(port_id, {'port': {'admin_state_up': False}})
                self._do_test_vm_connectivity_admin_state_up()
                self.network_client.update_port(port_id, {'port': {'admin_state_up': True}})

    def _check_public_network_connectivity(self):
        ssh_login = self.config.compute.image_ssh_user
        private_key = self.keypairs[self.tenant_id].private_key
        try:
            for server, floating_ips in self.floating_ips.iteritems():
                for floating_ip in floating_ips:
                    ip_address = floating_ip.floating_ip_address
                    self._check_vm_connectivity(ip_address, ssh_login, private_key)
        except Exception as exc:
            LOG.exception(exc)
            debug.log_ip_ns()
            raise exc

    @attr(type='smoke')
    @services('compute', 'network')
    def test_network_adminstateup(self):
        self.basic_scenario()
        LOG.info("Starting Router test")
        self._check_vm_connectivity_router()
        self._check_public_network_connectivity()
        pprint("End of Rotuer test")
        LOG.info("Starting Network test")
        self._check_vm_connectivity_net()
        self._check_public_network_connectivity()
        pprint("End of Net test")
        LOG.info("Starting Port test")
        self._check_vm_connectivity_port()
        pprint("End of Port test")
        self._check_public_network_connectivity()


