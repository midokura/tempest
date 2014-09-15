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


from tempest.openstack.common import log as logging
from tempest.scenario.midokura.midotools import helper
from tempest.scenario.midokura.midotools import scenario
from tempest import test

LOG = logging.getLogger(__name__)
CIDR1 = "10.10.10.0/24"


class TestNetworkBasicDhcpDisable(scenario.TestScenario):
    """
        Scenario:
            Ability to disable DHCP
        Prerequisite:
            1 tenant
            1 network
            1 vm
        Steps:
            1) spawn the VM
            2) Disable the DHCP
            3) try to renew DHCP
        Expected result:
            can't renew the dhcp
    """

    @classmethod
    def setUpClass(cls):
        super(TestNetworkBasicDhcpDisable, cls).setUpClass()
        cls.check_preconditions()

    def setUp(self):
        super(TestNetworkBasicDhcpDisable, self).setUp()
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
            "allocation_pools": None,
            "dns": [],
            "routes": [],
            "routers": None,
        }
        networkA = {
            'subnets': [subnetA],
            'servers': [serverB],
        }
        tenantA = {
            'networks': [networkA],
            'tenant_id': None,
            'type': 'default',
            'hasgateway': True,
            'MasterKey': False,
        }
        self.scenario = {
            'tenants': [tenantA],
        }

    # this should be ported to "linux_client" class
    def _do_dhcp_lease(self, remote_ip,pk):
        try:
            ssh_client = self.setup_tunnel([(remote_ip, pk)])
            pid = ssh_client.exec_command("ps fuax | grep udhcp | "
                                          "awk '{print $1}'").split("\n")[0]
            LOG.info(pid)
            out = ssh_client.exec_command("sudo kill -USR1 %s" % pid)
            LOG.info(out)
        except Exception as inst:
            LOG.info(inst.args)
            raise
