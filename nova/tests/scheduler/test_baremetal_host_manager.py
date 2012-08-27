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
from nova.compute import vm_states

"""
Tests For BaremetalHostManager.
"""

import mox

from nova.tests import utils

from nova import db
from nova import exception
from nova import flags
from nova.openstack.common import timeutils
from nova.scheduler import baremetal_host_manager as bhm
from nova.scheduler import host_manager
from nova import test


FLAGS = flags.FLAGS
UUID_A = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
UUID_B = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
UUID_C = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
NODES_FREE = [
        dict(id=1, cpus=2, memory_mb=512, local_gb=100, instance_uuid=None),
        dict(id=2, cpus=2, memory_mb=1024, local_gb=200, instance_uuid=None),
        dict(id=3, cpus=1, memory_mb=2048, local_gb=300, instance_uuid=None),
]
NODES_USED = [
        dict(id=4, cpus=2, memory_mb=4096, local_gb=400, instance_uuid=UUID_A),
]

NODES = []
NODES.extend(NODES_FREE)
NODES.extend(NODES_USED)

NODE_CAPS = []
for n in NODES:
    NODE_CAPS.append({'node': n}) 


class NodeStateBuilderTestCase(test.TestCase):
    def test_create_host_state_map_non_baremetal(self):
        caps = {'compute': {}}

        hm = bhm.BaremetalHostManager()
        m = hm.create_host_state_map(
            "host1",
            "compute",
            capabilities=caps)
        self.assertTrue(m["host1"].__class__ is host_manager.HostState)

    def test_canonicalize_node(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             }
        dn = bhm._canonicalize_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 2)
        self.assertEqual(dn.get('memory_mb'), 3)
        self.assertEqual(dn.get('local_gb'), 4)
        self.assertTrue(dn['instance_uuid'] is None)

    def test_canonicalize_node_with_instance_uuid(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             'instance_uuid': 'uuuuiidd'
             }
        dn = bhm._canonicalize_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 2)
        self.assertEqual(dn.get('memory_mb'), 3)
        self.assertEqual(dn.get('local_gb'), 4)
        self.assertEqual(dn.get('instance_uuid'), 'uuuuiidd')

    def test_canonicalize_node_without_id(self):
        n = {'id': None,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             }
        dn = bhm._canonicalize_node(n)
        self.assertTrue(dn is None)

    def test_canonicalize_node_registration_not_done(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             'registration_status': '!done',
             }
        dn = bhm._canonicalize_node(n)
        self.assertTrue(dn is None)

    def test_canonicalize_node_with_spec_none(self):
        n = {'id': 1,
             'local_gb': 4,
             }
        dn = bhm._canonicalize_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 0)
        self.assertEqual(dn.get('memory_mb'), 0)
        self.assertEqual(dn.get('local_gb'), 4)

    def test_map_nodes(self):
        n, i = bhm._map_nodes(NODE_CAPS)

        self.assertEqual(n[NODE_CAPS[0]['node']['id']], NODE_CAPS[0])
        self.assertEqual(n[NODE_CAPS[1]['node']['id']], NODE_CAPS[1])
        self.assertEqual(n[NODE_CAPS[2]['node']['id']], NODE_CAPS[2])
        node3_cap = NODE_CAPS[3].copy()
        del(node3_cap['node']['instance_uuid'])
        self.assertEqual(n[NODE_CAPS[3]['node']['id']], node3_cap)
        self.assertEqual(len(n), 4)

        self.assertEqual(i[UUID_A], NODE_CAPS[3]['node']['id'])
        self.assertEqual(len(i), 1)

    def test_get_deleted_instances_from_db(self):
        context = utils.get_test_admin_context()
        r = bhm._get_deleted_instances_from_db(context, 'host1', 0)
        self.assertEqual(r, [])

        db.instance_create(context, {'host': 'host1', 'uuid': UUID_A})
        db.instance_create(context, {'host': 'host1', 'uuid': UUID_B})
        db.instance_create(context, {'host': 'host2', 'uuid': UUID_C})
        db.instance_update(context, UUID_A, {'vm_state': vm_states.DELETED})
        db.instance_update(context, UUID_B, {'vm_state': vm_states.ACTIVE})
        db.instance_update(context, UUID_C, {'vm_state': vm_states.DELETED})
        db.instance_destroy(context, UUID_A)
        db.instance_destroy(context, UUID_C)

        r = bhm._get_deleted_instances_from_db(context, 'host1', 0)
        self.assertEqual(r[0]['uuid'], UUID_A)
        self.assertEqual(len(r), 1)

        # Parameter 'since' works
        r = bhm._get_deleted_instances_from_db(context, 'host1',
                                               timeutils.utcnow_ts() + 1000)
        self.assertEqual(len(r), 0)

    def test_init(self):
        b = bhm.NodeStateBuilder(NODE_CAPS)
        self.assertEqual(len(b.nodes), 4)
        self.assertEqual(len(b._instances), 1)
        return b

    def _check_used_none(self, builder):
        self.assertEqual(len(builder.nodes), 4)
        self.assertEqual(len(builder._instances), 0)

    def _check_used_3(self, builder):
        self.assertEqual(len(builder.nodes), 3)
        self.assertEqual(builder._instances[UUID_A], NODES_USED[0]['id'])
        self.assertEqual(len(builder._instances), 1)

    def test_consume_from_instance_known_uuid(self):
        inst = {'uuid': UUID_A, 'vcpus': 1, 'memory_mb': 2048}
        b = self.test_init()
        b._consume(inst)
        self._check_used_3(b)

    def test_consume_from_instance_unknown_uuid(self):
        inst = {'uuid': UUID_B, 'vcpus': 1, 'memory_mb': 2048}
        s = self.test_update_from_compute_node()
        s.consume_from_instance(inst)
        self.assertEqual(len(s._nodes), 2)
        self.assertIn(UUID_A, s._instances)
        self.assertIn(UUID_B, s._instances)
        self.assertEqual(len(s._instances), 2)
        self.assertEqual(s.free_ram_mb, 1024)

    def test_consume_from_instance_unknown_uuid_small(self):
        inst = {'uuid': UUID_B, 'vcpus': 1, 'memory_mb': 256}
        s = self.test_update_from_compute_node()
        s.consume_from_instance(inst)
        self.assertEqual(len(s._nodes), 2)
        self.assertIn(UUID_A, s._instances)
        self.assertIn(UUID_B, s._instances)
        self.assertEqual(len(s._instances), 2)
        # not changed since the biggest node is still free
        self.assertEqual(s.free_ram_mb, 2048)

    def test_consume_from_instance_without_uuid(self):
        s = self.test_update_from_compute_node()
        inst = {'uuid': None, 'vcpus': 1, 'memory_mb': 2048}
        s.consume_from_instance(inst)
        # _nodes is consumed, but _instances is unchanged
        self.assertEqual(len(s._nodes), 2)
        self.assertIn(UUID_A, s._instances)
        self.assertEqual(len(s._instances), 1)
        self.assertEqual(s.free_ram_mb, 1024)

    def test_consume_from_instance_not_capable(self):
        s = self.test_update_from_compute_node()
        # no suitable node
        inst = {'uuid': UUID_B, 'vcpus': 10000, 'memory_mb': 10000000}
        s.consume_from_instance(inst)
        # the biggest node in available nodes (id=3) is consumed
        self.assertEqual(len(s._nodes), 2)
        self.assertIn(UUID_A, s._instances)
        self.assertEqual(s._instances[UUID_B], NODES[2]['id'])
        self.assertEqual(len(s._instances), 2)
        self.assertEqual(s.free_ram_mb, 1024)


class BaremetalHostStateTestCase(test.TestCase):
    def test_is_baremetal(self):
        compute_caps = {
                'instance_type_extra_specs': {'baremetal_driver': 'test'}}
        self.assertTrue(bhm._is_baremetal(compute_caps))
        self.assertFalse(bhm._is_baremetal({}))

    def test_create_host_state_map_baremetal(self):
        compute_caps = {
                'instance_type_extra_specs': {'baremetal_driver': 'test'}}
        caps = {'compute': compute_caps}

        hm = bhm.BaremetalHostManager()
        m = hm.create_host_state_map(
            "host1",
            "compute",
            capabilities=caps)
        self.assertTrue(m["host1"].__class__ is bhm.BaremetalHostState)

    def test_create_host_state_map_non_baremetal(self):
        caps = {'compute': {}}

        hm = bhm.BaremetalHostManager()
        m = hm.create_host_state_map(
            "host1",
            "compute",
            capabilities=caps)
        self.assertTrue(m["host1"].__class__ is host_manager.HostState)

    def test_canonicalize_node(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             }
        dn = bhm._canonicalize_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 2)
        self.assertEqual(dn.get('memory_mb'), 3)
        self.assertEqual(dn.get('local_gb'), 4)
        self.assertTrue(dn['instance_uuid'] is None)

    def test_canonicalize_node_with_instance_uuid(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             'instance_uuid': 'uuuuiidd'
             }
        dn = bhm._canonicalize_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 2)
        self.assertEqual(dn.get('memory_mb'), 3)
        self.assertEqual(dn.get('local_gb'), 4)
        self.assertEqual(dn.get('instance_uuid'), 'uuuuiidd')

    def test_canonicalize_node_without_id(self):
        n = {'id': None,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             }
        dn = bhm._canonicalize_node(n)
        self.assertTrue(dn is None)

    def test_canonicalize_node_registration_not_done(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             'registration_status': '!done',
             }
        dn = bhm._canonicalize_node(n)
        self.assertTrue(dn is None)

    def test_canonicalize_node_with_spec_none(self):
        n = {'id': 1,
             'local_gb': 4,
             }
        dn = bhm._canonicalize_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 0)
        self.assertEqual(dn.get('memory_mb'), 0)
        self.assertEqual(dn.get('local_gb'), 4)

    def test_map_nodes(self):
        n, i = bhm._map_nodes(NODE_CAPS)

        self.assertEqual(n[NODE_CAPS[0]['node']['id']], NODE_CAPS[0])
        self.assertEqual(n[NODE_CAPS[1]['node']['id']], NODE_CAPS[1])
        self.assertEqual(n[NODE_CAPS[2]['node']['id']], NODE_CAPS[2])
        node3_cap = NODE_CAPS[3].copy()
        del(node3_cap['node']['instance_uuid'])
        self.assertEqual(n[NODE_CAPS[3]['node']['id']], node3_cap)
        self.assertEqual(len(n), 4)

        self.assertEqual(i[UUID_A], NODE_CAPS[3]['node']['id'])
        self.assertEqual(len(i), 1)

    def test_get_deleted_instances_from_db(self):
        context = utils.get_test_admin_context()
        r = bhm._get_deleted_instances_from_db(context, 'host1', 0)
        self.assertEqual(r, [])

        db.instance_create(context, {'host': 'host1', 'uuid': UUID_A})
        db.instance_create(context, {'host': 'host1', 'uuid': UUID_B})
        db.instance_create(context, {'host': 'host2', 'uuid': UUID_C})
        db.instance_update(context, UUID_A, {'vm_state': vm_states.DELETED})
        db.instance_update(context, UUID_B, {'vm_state': vm_states.ACTIVE})
        db.instance_update(context, UUID_C, {'vm_state': vm_states.DELETED})
        db.instance_destroy(context, UUID_A)
        db.instance_destroy(context, UUID_C)

        r = bhm._get_deleted_instances_from_db(context, 'host1', 0)
        self.assertEqual(r[0]['uuid'], UUID_A)
        self.assertEqual(len(r), 1)

        # Parameter 'since' works
        r = bhm._get_deleted_instances_from_db(context, 'host1',
                                               timeutils.utcnow_ts() + 1000)
        self.assertEqual(len(r), 0)

    def test_init(self):
        cap = {'timestamp': 1,
               'instance_type_extra_specs': {'baremetal_driver': 'test'},
               'nodes': NODES,
                }
        caps = {'compute': cap}
        s = bhm.BaremetalHostState(
            "host1",
            "compute",
            capabilities=caps)
        self.assertEqual(s.host, "host1")
        self.assertEqual(s.topic, "compute")
        self.assertEqual(s._nodes_from_capabilities, NODES)
        self.assertEqual(s.nodes is None)
        self.assertEqual(s.instances is None)
        return s

    def _check_used_none(self, hs):
        self.assertEqual(len(hs._nodes), 4)
        self.assertEqual(len(hs._instances), 0)
        self.assertEqual(hs.free_ram_mb, 4096)

    def _check_used_3(self, hs):
        self.assertEqual(len(hs._nodes), 3)
        self.assertEqual(hs._instances[UUID_A], NODES_USED[0]['id'])
        self.assertEqual(len(hs._instances), 1)
        self.assertEqual(hs.free_ram_mb, 2048)

    def test_update_from_compute_node(self):
        s = self.test_init()
        s.update_from_compute_node(None)
        self._check_used_3(s)
        return s

    def test_update_from_compute_node_with_terminated_inst(self):
        s = self.test_init()

        self.mox.StubOutWithMock(bhm, '_get_deleted_instances_from_db')
        bhm._get_deleted_instances_from_db(mox.IgnoreArg(), 'host1', 1)\
                .AndReturn([{'uuid': UUID_A}])
        self.mox.ReplayAll()

        s.update_from_compute_node(None)
        self._check_used_none(s)
        return s

    def test_update_from_compute_node_with_terminated_unknown_inst(self):
        s = self.test_init()

        self.mox.StubOutWithMock(bhm, '_get_deleted_instances_from_db')
        bhm._get_deleted_instances_from_db(mox.IgnoreArg(), 'host1', 1)\
                .AndReturn([{'uuid': UUID_B}])
        self.mox.ReplayAll()

        s.update_from_compute_node(None)
        self._check_used_3(s)
        return s

    def test_consume_from_instance_known_uuid(self):
        inst = {'uuid': UUID_A, 'vcpus': 1, 'memory_mb': 2048}
        s = self.test_update_from_compute_node()
        s.consume_from_instance(inst)
        self._check_used_3(s)

    def test_consume_from_instance_unknown_uuid(self):
        inst = {'uuid': UUID_B, 'vcpus': 1, 'memory_mb': 2048}
        s = self.test_update_from_compute_node()
        s.consume_from_instance(inst)
        self.assertEqual(len(s._nodes), 2)
        self.assertIn(UUID_A, s._instances)
        self.assertIn(UUID_B, s._instances)
        self.assertEqual(len(s._instances), 2)
        self.assertEqual(s.free_ram_mb, 1024)

    def test_consume_from_instance_unknown_uuid_small(self):
        inst = {'uuid': UUID_B, 'vcpus': 1, 'memory_mb': 256}
        s = self.test_update_from_compute_node()
        s.consume_from_instance(inst)
        self.assertEqual(len(s._nodes), 2)
        self.assertIn(UUID_A, s._instances)
        self.assertIn(UUID_B, s._instances)
        self.assertEqual(len(s._instances), 2)
        # not changed since the biggest node is still free
        self.assertEqual(s.free_ram_mb, 2048)

    def test_consume_from_instance_without_uuid(self):
        s = self.test_update_from_compute_node()
        inst = {'uuid': None, 'vcpus': 1, 'memory_mb': 2048}
        s.consume_from_instance(inst)
        # _nodes is consumed, but _instances is unchanged
        self.assertEqual(len(s._nodes), 2)
        self.assertIn(UUID_A, s._instances)
        self.assertEqual(len(s._instances), 1)
        self.assertEqual(s.free_ram_mb, 1024)

    def test_consume_from_instance_not_capable(self):
        s = self.test_update_from_compute_node()
        # no suitable node
        inst = {'uuid': UUID_B, 'vcpus': 10000, 'memory_mb': 10000000}
        s.consume_from_instance(inst)
        # the biggest node in available nodes (id=3) is consumed
        self.assertEqual(len(s._nodes), 2)
        self.assertIn(UUID_A, s._instances)
        self.assertEqual(s._instances[UUID_B], NODES[2]['id'])
        self.assertEqual(len(s._instances), 2)
        self.assertEqual(s.free_ram_mb, 1024)


BAREMETAL_COMPUTE_NODES = [
        dict(id=1, service_id=1, local_gb=10240, memory_mb=10240, vcpus=10,
             vcpus_used=0,
             free_ram_mb=10240,
             free_disk_gb=10240,
             service=dict(host='host1')),
        dict(id=2, service_id=2, local_gb=2048, memory_mb=1024, vcpus=2,
             vcpus_used=0,
             free_ram_mb=1024,
             free_disk_gb=2048,
             service=dict(host='host2')),
        dict(id=3, service_id=3, local_gb=2048, memory_mb=2048, vcpus=2,
             vcpus_used=0,
             free_ram_mb=2048,
             free_disk_gb=2048,
             service=dict(host='host3')),
        dict(id=4, service_id=4, local_gb=2048, memory_mb=2048, vcpus=7,
             vcpus_used=0,
             free_ram_mb=2048,
             free_disk_gb=2048,
             service=dict(host='host4')),
        # Broken entry
        dict(id=5, service_id=5, local_gb=1024, memory_mb=1024, vcpus=1,
             vcpus_used=0,
             free_ram_mb=1024,
             free_local_gb=1024,
             service=None),
]


auto_id = 0


def inst(**kwargs):
    d = kwargs.copy()
    d['root_gb'] = d.get('root_gb', 10)
    d['ephemeral_gb'] = d.get('ephemeral_gb', 20)
    d['memory_mb'] = d.get('memory_mb', 512)
    d['vcpus'] = d.get('vcpus', 1)
    return d


def node(**kwargs):
    d = kwargs.copy()
    if 'id' not in d:
        global auto_id
        auto_id += 1
        d['id'] = auto_id
    if 'cpus' not in d:
        d['cpus'] = 9999
    if 'local_gb' not in d:
        d['local_gb'] = 9999
    if 'instance_uuid' not in d:
        d['instance_uuid'] = None
    return d


BAREMETAL_INSTANCES = [
        inst(vcpus=1, host='host1', uuid='1'),
        inst(vcpus=1, host='host1', uuid='2'),
        inst(vcpus=1, host='host1', uuid='9'),

        inst(vcpus=2, host='host2', uuid='3'),
        inst(vcpus=1, host='host2', uuid='7'),

        inst(vcpus=3, host='host3', uuid='4'),
        inst(vcpus=1, host='host3', uuid='8'),

        inst(vcpus=4, host='host4', uuid='5'),
        inst(vcpus=2, host='host4', uuid='6'),
        # Broken host
        inst(vcpus=1, host=None, uuid='1000'),
        # No matching host
        inst(vcpus=1, host='hostz', uuid='2000'),
]


BAREMETAL_NODES_1 = [
        node(instance_uuid='1', memory_mb=8192),
        node(instance_uuid='2', memory_mb=4096),
        node(instance_uuid='9', memory_mb=1024),
        node(memory_mb=512),
        node(memory_mb=1024),
        node(memory_mb=2048),
        node(memory_mb=256),
        node(memory_mb=10240),
]

BAREMETAL_NODES_2 = [
        node(instance_uuid='3', memory_mb=10240),
        node(memory_mb=2048),
        node(memory_mb=2048),
        node(memory_mb=512),
        node(memory_mb=8192),
        node(memory_mb=1024),
        node(memory_mb=4096),
        node(memory_mb=512),
]

BAREMETAL_NODES_3 = [
        node(instance_uuid='4', memory_mb=8192),
        node(instance_uuid='7', memory_mb=10240),
        node(memory_mb=512),
        node(memory_mb=2048),
        node(memory_mb=1024),
        node(memory_mb=512),
]


class ComputeFilterClass1(object):
    def host_passes(self, *args, **kwargs):
        pass


class ComputeFilterClass2(object):
    def host_passes(self, *args, **kwargs):
        pass


class BaremetalHostManagerTestCase(test.TestCase):
    """Test case for HostManager class"""

    def setUp(self):
        super(BaremetalHostManagerTestCase, self).setUp()
        self.bhm = bhm.BaremetalHostManager()

    def test_choose_host_filters_not_found(self):
        self.flags(scheduler_default_filters='ComputeFilterClass3')
        self.bhm.filter_classes = [ComputeFilterClass1, ComputeFilterClass2]
        self.assertRaises(exception.SchedulerHostFilterNotFound,
                self.bhm._choose_host_filters, None)

    def test_choose_host_filters(self):
        self.flags(scheduler_default_filters=['ComputeFilterClass2'])
        self.bhm.filter_classes = [ComputeFilterClass1, ComputeFilterClass2]

        # Test 'compute' returns 1 correct function
        filter_fns = self.bhm._choose_host_filters(None)
        self.assertEqual(len(filter_fns), 1)
        self.assertEqual(filter_fns[0].__func__,
                ComputeFilterClass2.host_passes.__func__)

    def test_filter_hosts(self):
        topic = 'fake_topic'

        filters = ['fake-filter1', 'fake-filter2']
        fake_host1 = bhm.BaremetalHostState('host1', topic)
        fake_host2 = bhm.BaremetalHostState('host2', topic)
        hosts = [fake_host1, fake_host2]
        filter_properties = 'fake_properties'

        self.mox.StubOutWithMock(self.bhm, '_choose_host_filters')
        self.mox.StubOutWithMock(fake_host1, 'passes_filters')
        self.mox.StubOutWithMock(fake_host2, 'passes_filters')

        self.bhm._choose_host_filters(None).AndReturn(filters)
        fake_host1.passes_filters(filters, filter_properties).AndReturn(True)
        fake_host2.passes_filters(filters, filter_properties).AndReturn(True)

        self.mox.ReplayAll()
        filtered_hosts = self.bhm.filter_hosts(hosts,
                filter_properties, filters=None)
        self.assertEqual(len(filtered_hosts), 2)
        self.assertEqual(filtered_hosts[0], fake_host1)
        self.mox.VerifyAll()

    def test_update_service_capabilities(self):
        service_states = self.bhm.service_states
        self.assertDictMatch(service_states, {})
        self.mox.StubOutWithMock(timeutils, 'utcnow')
        timeutils.utcnow().AndReturn(31337)
        timeutils.utcnow().AndReturn(31338)
        timeutils.utcnow().AndReturn(31339)
        timeutils.utcnow().AndReturn(31340)

        host1_compute_capabs = dict(free_memory=1234, timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'})
        host1_volume_capabs = dict(free_disk=4321, timestamp=1)

        host2_compute_capabs = dict(free_memory=8756, timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'})
        host3_compute_capabs = dict(free_memory=2048, timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'})

        self.mox.ReplayAll()

        self.bhm.update_service_capabilities('volume',
                'host1', host1_volume_capabs)
        self.bhm.update_service_capabilities('compute',
                'host1', host1_compute_capabs)
        self.bhm.update_service_capabilities('compute',
                'host2', host2_compute_capabs)
        self.bhm.update_service_capabilities('compute',
                'host3', host3_compute_capabs)

        # Make sure dictionary isn't re-assigned
        self.assertEqual(self.bhm.service_states,
                service_states)
        # Make sure original dictionary wasn't copied
        self.assertEqual(host1_compute_capabs['timestamp'], 1)
        self.assertEqual(
            host1_compute_capabs['instance_type_extra_specs'][\
            'baremetal_driver'],
            'test')

        host1_compute_capabs['timestamp'] = 31338
        host1_volume_capabs['timestamp'] = 31337
        host2_compute_capabs['timestamp'] = 31339
        host3_compute_capabs['timestamp'] = 31340

        expected = {'host3': {'compute': host3_compute_capabs},
                    'host2': {'compute': host2_compute_capabs},
                    'host1': {'compute': host1_compute_capabs,
                              'volume': host1_volume_capabs}}

        self.assertDictMatch(service_states, expected)
        self.mox.VerifyAll()

    def test_get_all_host_states(self):
        self.flags(reserved_host_memory_mb=512,
                reserved_host_disk_mb=1024)

        def fake_get_instances_from_db(context, host):
            l = []
            for i in BAREMETAL_INSTANCES:
                if i['host'] == host:
                    l.append(i)
            return l

        def fake_get_deleted_instances_from_db(context, host, since):
            return []

        context = 'fake_context'
        topic = 'compute'
        self.mox.StubOutWithMock(db, 'compute_node_get_all')
        self.mox.StubOutWithMock(host_manager.LOG, 'warn')
        #self.mox.StubOutWithMock(db, 'instance_get_all')
        self.stubs.Set(timeutils, 'utcnow', lambda: 31337)
        self.stubs.Set(bhm, '_get_instances_from_db',
                       fake_get_instances_from_db)
        self.stubs.Set(bhm, '_get_deleted_instances_from_db',
                       fake_get_deleted_instances_from_db)

        db.compute_node_get_all(context).AndReturn(BAREMETAL_COMPUTE_NODES)
        # Invalid service
        host_manager.LOG.warn("No service for compute ID 5")
        self.mox.ReplayAll()

        host1_compute_capabs = dict(
                free_memory=1234, host_memory=5678,
                timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'},
                nodes=BAREMETAL_NODES_1)
        host2_compute_capabs = dict(
                free_memory=1234, host_memory=5678,
                timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'},
                nodes=BAREMETAL_NODES_2)
        host3_compute_capabs = dict(
                free_memory=1234, host_memory=5678,
                timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'},
                nodes=BAREMETAL_NODES_3)
        host4_compute_capabs = dict(
                free_memory=1234, host_memory=5678,
                timestamp=1)

        self.bhm.update_service_capabilities('compute',
                'host1', host1_compute_capabs)
        self.bhm.update_service_capabilities('compute',
                'host2', host2_compute_capabs)
        self.bhm.update_service_capabilities('compute',
                'host3', host3_compute_capabs)
        self.bhm.update_service_capabilities('compute',
                'host4', host4_compute_capabs)

        host_states = self.bhm.get_all_host_states(context, topic)

        for i in BAREMETAL_INSTANCES:
            if i['host'] not in host_states:
                continue
            host_states[i['host']].consume_from_instance(i)

        num_bm_nodes = len(BAREMETAL_COMPUTE_NODES)

        # not contains broken entry
        self.assertEqual(len(host_states), num_bm_nodes - 1)
        self.assertIn('host1', host_states)
        self.assertIn('host2', host_states)
        self.assertIn('host3', host_states)
        self.assertIn('host4', host_states)

        # check returned value
        self.assertEqual(host_states['host1'].free_ram_mb, 10240)
        self.assertEqual(host_states['host2'].free_ram_mb, 8192)
        self.assertEqual(host_states['host3'].free_ram_mb, 2048)
        self.assertEqual(host_states['host4'].free_ram_mb, 512)
        self.assertEqual(host_states['host4'].vcpus_used, 6)

        self.mox.VerifyAll()
