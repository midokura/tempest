__author__ = 'Albert'
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


from tempest import config
from tempest.openstack.common import log as logging
from tempest.test import attr
from tempest.test import services
from tempest.common import ssh
from tempest.scenario.midokura.midotools import scenario


CONF = config.CONF
LOG = logging.getLogger(__name__)
CIDR1 = "10.10.1.0/24"

class TestMetaData(scenario.TestScenario):

    @classmethod
    def setUpClass(cls):
        super(TestMetaData, cls).setUpClass()
        cls.scenario = {}

    def setUp(self):
        super(TestMetaData, self).setUp()
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

    def _check_metadata(self):
        ssh_login = CONF.compute.image_ssh_user
        private_key = self.keypairs[self.tenant_id].private_key
        try:
            server, floating_ip = self.floating_ip_tuple
            ip_address = floating_ip.floating_ip_address
            private_key = self.servers[server].private_key
            ssh_client = ssh.Client(ip_address, ssh_login,
                        pkey=private_key,
                        timeout=self.config.compute.ssh_timeout)
            result = ssh_client.exec_command("curl http://169.254.169.254")
            _expected = "1.0\n2007-01-19\n2007-03-01\n2007-08-29\n2007-10-10\n" \
                        "2007-12-15\n2008-02-01\n2008-09-01\n2009-04-04\nlatest"
            self.assertEqual(_expected, result)
        except Exception as exc:
            raise exc

    @attr(type='smoke')
    @services('compute', 'network')
    def test_network_basic_metadata(self):
        self._check_metadata()
