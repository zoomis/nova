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

from nova import flags
from nova.scheduler import baremetal_host_manager
from nova.scheduler import host_manager
from nova import test


FLAGS = flags.FLAGS


NODES_FREE = [
        dict(id=1, cpus=2, memory_mb=512, local_gb=100, instance_uuid=None),
        dict(id=2, cpus=2, memory_mb=1024, local_gb=200, instance_uuid=None),
        dict(id=3, cpus=1, memory_mb=2048, local_gb=300, instance_uuid=None),
]

NODES_USED = [
        dict(id=4, cpus=2, memory_mb=4096, local_gb=400, instance_uuid='A'),
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

    def test_dict_node(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             }
        dn = baremetal_host_manager._dict_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 2)
        self.assertEqual(dn.get('memory_mb'), 3)
        self.assertEqual(dn.get('local_gb'), 4)
        self.assertTrue('instance_uuid' in dn)
        self.assertTrue(dn['instance_uuid'] is None)

    def test_dict_node_with_instance_uuid(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             'instance_uuid': 'uuuuiidd'
             }
        dn = baremetal_host_manager._dict_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 2)
        self.assertEqual(dn.get('memory_mb'), 3)
        self.assertEqual(dn.get('local_gb'), 4)
        self.assertEqual(dn.get('instance_uuid'), 'uuuuiidd')

    def test_dict_node_without_id(self):
        n = {'id': None,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             }
        dn = baremetal_host_manager._dict_node(n)
        self.assertTrue(dn is None)

    def test_dict_node_registration_not_done(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             'registration_status': '!done',
             }
        dn = baremetal_host_manager._dict_node(n)
        self.assertTrue(dn is None)

    def test_dict_node_with_spec_none(self):
        n = {'id': 1,
             'local_gb': 4,
             }
        dn = baremetal_host_manager._dict_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 0)
        self.assertEqual(dn.get('memory_mb'), 0)
        self.assertEqual(dn.get('local_gb'), 4)

    def test_map_nodes(self):
        n, i = baremetal_host_manager._map_nodes(NODES)

        self.assertEqual(n[1], NODES_FREE[0])
        self.assertEqual(n[2], NODES_FREE[1])
        self.assertEqual(n[3], NODES_FREE[2])
        self.assertEqual(len(n), 3)

        self.assertEqual(i['A'], NODES_USED[0])
        self.assertEqual(len(i), 1)

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
        self.assertEqual(len(s._nodes), 3)
        self.assertEqual(len(s._instances), 1)
        self.assertEqual(s.free_ram_mb, 2048)
        self.assertEqual(s.free_disk_mb, 300 * 1024)
        self.assertEqual(s.vcpus_total, 1)
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
        self.assertEqual(len(s._instances), 1)
        self.assertEqual(s.free_ram_mb, 0)
        self.assertEqual(s.free_disk_mb, 0)
        self.assertEqual(s.vcpus_total, 0)
        self.assertEqual(s.vcpus_used, 0)
        return s

    def test_consume_from_instance(self):
        inst = {'uuid': 'X', 'vcpus': 1, 'memory_mb': 2048}
        s = self.test_init()
        s.consume_from_instance(inst)
        self.assertEqual(len(s._nodes), 2)
        self.assertTrue('X' in s._instances)
        self.assertEqual(len(s._instances), 2)
        self.assertEqual(s.free_ram_mb, 1024)
        self.assertEqual(s.free_disk_mb, 200 * 1024)
        self.assertEqual(s.vcpus_total, 2)
        self.assertEqual(s.vcpus_used, 0)

    def test_consume_from_instance_small(self):
        inst = {'uuid': 'X', 'vcpus': 1, 'memory_mb': 256}
        s = self.test_init()
        s.consume_from_instance(inst)
        self.assertEqual(len(s._nodes), 2)
        self.assertTrue('X' in s._instances)
        self.assertEqual(len(s._instances), 2)
        # the following is not changed since the biggest node is still free
        self.assertEqual(s.free_ram_mb, 2048)
        self.assertEqual(s.free_disk_mb, 300 * 1024)
        self.assertEqual(s.vcpus_total, 1)
        self.assertEqual(s.vcpus_used, 0)

    def test_consume_from_instance_without_uuid(self):
        inst = {'uuid': None, 'vcpus': 1, 'memory_mb': 2048}
        s = self.test_init()
        s.consume_from_instance(inst)
        # _nodes is consumed, but _instances is unchanged
        self.assertEqual(len(s._nodes), 2)
        self.assertFalse('X' in s._instances)
        self.assertEqual(len(s._instances), 1)
        self.assertEqual(s.free_ram_mb, 1024)
        self.assertEqual(s.free_disk_mb, 200 * 1024)
        self.assertEqual(s.vcpus_total, 2)
        self.assertEqual(s.vcpus_used, 0)

    def test_consume_from_instance_without_free_nodes(self):
        # no suitable node
        inst = {'uuid': 'X', 'vcpus': 300, 'memory_mb': 100000}
        s = self.test_init_without_free_nodes()
        s.consume_from_instance(inst)
        self.assertEqual(len(s._nodes), 0)
        self.assertFalse('X' in s._instances)
        self.assertEqual(len(s._instances), 1)
        self.assertEqual(s.free_ram_mb, 0)
        self.assertEqual(s.free_disk_mb, 0)
        self.assertEqual(s.vcpus_total, 0)
        self.assertEqual(s.vcpus_used, 0)
