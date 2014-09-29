# Copyright 2014 Midokura SARL.
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

import testtools

from tempest.api.network import common as net_common
from tempest.common.utils import data_utils
from tempest import config
from tempest.openstack.common import log as logging
from tempest.scenario import manager
from tempest.services.network import resources as net_resources
from tempest import test

import yaml

CONF = config.CONF
LOG = logging.getLogger(__name__)


class TestNetworkBasicScenario(manager.NetworkScenarioTest):

    """
    """

    @classmethod
    def setUpClass(cls):
        super(TestNetworkBasicScenario, cls).setUpClass()
        cls.check_preconditions()
        if not (CONF.network.tenant_networks_reachable
                or CONF.network.public_network_id):
            msg = ('Either tenant_networks_reachable must be "true", or '
                   'public_network_id must be defined.')
            cls.enabled = False
            raise cls.skipException(msg)

    def _setup_topology(
            self,
            yaml_topology='./network_scenarios/scenario.yaml'):
        from pprint import pprint

        with open(yaml_topology, 'r') as yaml_topology:
            topology = yaml.load(yaml_topology)
            for net in topology['networks']:
                body = dict(
                    network=dict(
                        name=net['name'],
                        tenant_id=self.tenant_id
                    ),
                )
                network = self._create_network_from_body(body)
                for snet in net['subnets']:
                    for srouter in snet['routers']:
                        body = dict(
                                router=dict(
                                    name=srouter['name'],
                                    admin_state_up=True,
                                    tenant_id=self.tenant_id
                                    )
                                )
                    body = dict(
                            subnet = dict(
                                name=snet['name'],
                                ip_version=4,
                                network_id=network.id,
                                tenant_id=self.tenant_id,
                                cidr=snet['cidr'],
                                enable_dhcp=snet['enable_dhcp'],
                                dns_nameservers=snet['dns_nameservers'],
                                allocation_pools=snet['allocation_pools']
                                )
                            )
                    subnet = self._create_subnet_from_body(body)
                    subnet.add_to_router(router.id)
            for secgroup in topology['security_groups']:
                sg = self._create_security_group_neutron(self.tenant_id)
                rules =
                self._create_security_group_rule_list(rule_dict=secgroup,
                        secgroup=sg.id)


    def _create_network_from_body(self, body):
        result =  self.network_client.create_network(body=body)
        network = net_common.DeletableNetwork(client=self.network_client,
                **result['network'])
        self.assertEqual(network.name, body['network']['name'])
        self.addCleanup(self.delete_wrapper, network)
        return network

    def _create_router_from_body(self, body):
        result = self.network_client.create_router(body=body)
        router = net_common.DeletableRouter(client=self.network_client,
                **result['router'])
        self.addCleanup(self.delete_wrapper, router)
        return router

    def _create_subnet_from_body(self, body):
        result = self.network_client.create_subnet(body=body)
        subnet = net_common.DeletableSubnet(client=self.network_client,
                **result['subnet'])
        self.addCleanup(self.delete_wrapper, subnet)
        return subnet

    def _create_security_group_rule_list(self, rule_dict=None, secgroup=None):
        client = self.network_client()
        rules = []
        if not rule_dict:
            rulesets = []
        else:
            rulesets = rule_dict
        for ruleset in rulesets:
            for r_direction in ['ingress', 'egress']:
                ruleset['direction'] = r_direction
                try:
                    sg_rule = self._create_security_group_rule(
                            client=client, secgroup=secgroup, **ruleset)
                except exc.NeutronClientException as ex:
                    if not (ex.status_code is 409 and 'Security group rule'
                            ' already exists' in ex.message):
                        raise ex
                else:
                    self.assertEqual(r_direction, sg_rule.direction)
                    rules.append(sg_rule)
        return rules



    @test.services('compute', 'network')
    def test_topology(self):
        self._setup_topology()
