# Copyright (c) 2012 NTT DOCOMO, INC.
# Copyright (c) 2011 OpenStack, LLC
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
"""
Tests For BaremetalHostManager.
"""

import datetime

from nova import db
from nova import exception
from nova import flags
from nova.openstack.common import timeutils
from nova.scheduler import baremetal_host_manager, host_manager
from nova import test
from nova.tests.scheduler import fakes
from nova import utils
from nova.virt.baremetal import db as bmdb


FLAGS = flags.FLAGS


BAREMETAL_COMPUTE_NODES = [
        dict(id=1, service_id=1, local_gb=10240, memory_mb=10240, vcpus=10,
                service=dict(host='host1', disabled=False)),
        dict(id=2, service_id=2, local_gb=2048, memory_mb=1024, vcpus=2,
                service=dict(host='host2', disabled=True)),
        dict(id=3, service_id=3, local_gb=2048, memory_mb=2048, vcpus=2,
                service=dict(host='host3', disabled=True)),
        dict(id=4, service_id=4, local_gb=2048, memory_mb=2048, vcpus=2,
                service=dict(host='host4', disabled=True)),
        # Broken entry
        dict(id=5, service_id=5, local_gb=1024, memory_mb=1024, vcpus=1,
                service=None),
]

BAREMETAL_INSTANCES = [
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                host='host1'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                host='host1'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=2,
                host='host2'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=3,
                host='host3'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=4,
                host='host4'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=2,
                host='host4'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                host='host3'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                host='host2'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=3,
                host='host1'),
        # Broken host
        dict(root_gb=1024, ephemeral_gb=0, memory_mb=1024, vcpus=1,
                host=None),
        # No matching host
        dict(root_gb=1024, ephemeral_gb=0, memory_mb=1024, vcpus=1,
                host='hostz'),
]

BAREMETAL_NODES = [
        dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.110',
                memory_mb=512, local_gb=0),
        dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.110',
                memory_mb=2048, local_gb=0),
]

BAREMETAL_NODES_1 = [
        dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=512, local_gb=0),
        dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=1024, local_gb=0),
        dict(cpus=2, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=2048, local_gb=0),
        dict(cpus=2, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=1024, local_gb=0),
        dict(cpus=3, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=4096, local_gb=0),
        dict(cpus=3, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=8192, local_gb=0),
        # No matching host
        dict(cpus=1, instance_uuid='1', ipmi_address='172.27.2.111',
                memory_mb=512, local_gb=0),
        dict(cpus=4, instance_uuid='1', ipmi_address='172.27.2.111',
                memory_mb=10240, local_gb=0),
]

BAREMETAL_NODES_2 = [
        dict(cpus=3, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=2048, local_gb=0),
        dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=1024, local_gb=0),
        dict(cpus=2, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=512, local_gb=0),
        dict(cpus=3, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=8192, local_gb=0),
        dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=1024, local_gb=0),
        dict(cpus=2, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=4096, local_gb=0),
        # No matching host
        dict(cpus=1, instance_uuid='2', ipmi_address='172.27.2.112',
                memory_mb=512, local_gb=0),
        dict(cpus=4, instance_uuid='2', ipmi_address='172.27.2.112',
                memory_mb=10240, local_gb=0),
]

BAREMETAL_NODES_3 = [
        dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.113',
                memory_mb=512, local_gb=0),
        dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.113',
                memory_mb=2048, local_gb=0),
        dict(cpus=5, instance_uuid=None, ipmi_address='172.27.2.113',
                memory_mb=8192, local_gb=0),
        dict(cpus=5, instance_uuid=None, ipmi_address='172.27.2.113',
                memory_mb=1024, local_gb=0),
        # No matching host
        dict(cpus=1, instance_uuid='3', ipmi_address='172.27.2.113',
                memory_mb=512, local_gb=0),
        dict(cpus=4, instance_uuid='3', ipmi_address='172.27.2.113',
                memory_mb=10240, local_gb=0),
]


BAREMETAL_NODES_4 = [
        dict(cpus=5, instance_uuid=None, ipmi_address='172.27.2.114',
                memory_mb=512, local_gb=0),
        dict(cpus=5, instance_uuid=None, ipmi_address='172.27.2.114',
                memory_mb=8192, local_gb=0),
        dict(cpus=6, instance_uuid=None, ipmi_address='172.27.2.114',
                memory_mb=512, local_gb=0),
        dict(cpus=6, instance_uuid=None, ipmi_address='172.27.2.114',
                memory_mb=8192, local_gb=0),
        # No matching host
        dict(cpus=1, instance_uuid='4', ipmi_address='172.27.2.114',
                memory_mb=512, local_gb=0),
        dict(cpus=4, instance_uuid='4', ipmi_address='172.27.2.114',
                memory_mb=10240, local_gb=0),
]


class ComputeFilterClass1(object):
    def host_passes(self, *args, **kwargs):
        pass


class ComputeFilterClass2(object):
    def host_passes(self, *args, **kwargs):
        pass


NODES_FREE = [
        dict(id=1, cpus=3, instance_uuid=None,
                memory_mb=2048, local_gb=100),
        dict(id=2, cpus=4, instance_uuid=None,
                memory_mb=1024, local_gb=200),
        dict(id=3, cpus=2, instance_uuid=None,
                memory_mb=512, local_gb=300),
        dict(id=4, cpus=3, instance_uuid=None,
                memory_mb=8192, local_gb=400),
        dict(id=5, cpus=4, instance_uuid=None,
                memory_mb=1024, local_gb=500),
        dict(id=6, cpus=2, instance_uuid=None,
                memory_mb=4096, local_gb=600),
]

NODES_USED = [
        dict(id=7, cpus=1, instance_uuid='A',
                memory_mb=512, local_gb=700),
        dict(id=8, cpus=4, instance_uuid='B',
                memory_mb=10240, local_gb=800),
]

NODES = []
NODES.extend(NODES_FREE)
NODES.extend(NODES_USED)

class BaremetalHostStateTestCase(test.TestCase):
    def test_new_baremetal(self):
        compute_caps = {
                'instance_type_extra_specs': {'baremetal_driver': 'test'}}
        caps = {'compute': compute_caps}

        host_state = baremetal_host_manager.new_host_state(
            None,
            "host1",
            "compute",
            capabilities=caps)
        self.assertEquals(host_state.host, "host1")
        self.assertEquals(host_state.topic, "compute")
        self.assertIs(host_state.__class__,
                      baremetal_host_manager.BaremetalHostState)
        self.assertEquals(host_state.service, {})

    def test_new_non_baremetal(self):
        compute_caps = {}
        caps = {'compute': compute_caps}

        host_state = baremetal_host_manager.new_host_state(
            None,
            "host1",
            "compute",
            capabilities=caps)
        self.assertEquals(host_state.host, "host1")
        self.assertEquals(host_state.topic, "compute")
        self.assertIs(host_state.__class__, host_manager.HostState)
        self.assertEquals(host_state.service, {})

    def test_map_nodes(self):
        n, i = baremetal_host_manager._map_nodes(NODES)

        self.assertEqual(n[1], NODES_FREE[0])
        self.assertEqual(n[2], NODES_FREE[1])
        self.assertEqual(n[3], NODES_FREE[2])
        self.assertEqual(n[4], NODES_FREE[3])
        self.assertEqual(n[5], NODES_FREE[4])
        self.assertEqual(n[6], NODES_FREE[5])
        self.assertEqual(len(n), 6)

        self.assertEqual(i['A'], NODES_USED[0])
        self.assertEqual(i['B'], NODES_USED[1])
        self.assertEqual(len(i), 2)

    def test_init(self):
        cap = {'timestamp': 1,
               'instance_type_extra_specs': {'baremetal_driver': 'test'},
               'nodes': NODES,
                }
        caps = {'compute': cap}
        s = baremetal_host_manager.new_host_state(
            None,
            "host1",
            "compute",
            capabilities=caps)
        self.assertEqual(s.host, "host1")
        self.assertEqual(s.topic, "compute")
        self.assertEqual(s._nodes_from_capabilities, NODES)
        self.assertEqual(len(s._nodes), 6)
        self.assertEqual(len(s._instances), 2)
        self.assertEqual(s.free_ram_mb, 8192)
        self.assertEqual(s.free_disk_mb, 400 * 1024)
        self.assertEqual(s.vcpus_total, 3)
        self.assertEqual(s.vcpus_used, 0)
        return s
    
    def test_init_without_free_nodes(self):
        cap = {'timestamp': 1,
               'instance_type_extra_specs': {'baremetal_driver': 'test'},
               'nodes': NODES_USED,
                }
        caps = {'compute': cap}
        s = baremetal_host_manager.new_host_state(
            None,
            "host1",
            "compute",
            capabilities=caps)
        self.assertEqual(s.host, "host1")
        self.assertEqual(s.topic, "compute")
        self.assertEqual(s._nodes_from_capabilities, NODES_USED)
        self.assertEqual(len(s._nodes), 0)
        self.assertEqual(len(s._instances), 2)
        self.assertEqual(s.free_ram_mb, 0)
        self.assertEqual(s.free_disk_mb, 0)
        self.assertEqual(s.vcpus_total, 0)
        self.assertEqual(s.vcpus_used, 0)
        return s
    
    def test_consume_from_instance(self):
        inst = {'uuid': 'X', 'vcpus': 3, 'memory_mb': 7000}
        s = self.test_init()
        s.consume_from_instance(inst)
        self.assertEqual(len(s._nodes), 5)
        self.assertTrue('X' in s._instances)
        self.assertEqual(len(s._instances), 3)
        self.assertEqual(s.free_ram_mb, 4096)
        self.assertEqual(s.free_disk_mb, 600 * 1024)
        self.assertEqual(s.vcpus_total, 2)
        self.assertEqual(s.vcpus_used, 0)

    def test_consume_from_instance_without_free_nodes(self):
        inst = {'uuid': 'X', 'vcpus': 3, 'memory_mb': 7000}
        s = self.test_init_without_free_nodes()
        s.consume_from_instance(inst)
        self.assertEqual(len(s._nodes), 0)
        self.assertFalse('X' in s._instances)
        self.assertEqual(len(s._instances), 2)
        self.assertEqual(s.free_ram_mb, 0)
        self.assertEqual(s.free_disk_mb, 0)
        self.assertEqual(s.vcpus_total, 0)
        self.assertEqual(s.vcpus_used, 0)
