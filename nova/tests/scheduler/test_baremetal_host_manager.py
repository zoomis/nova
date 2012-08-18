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

from nova import db
from nova import exception
from nova import flags
from nova.openstack.common import timeutils
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
        self.assertTrue(host_state.__class__ is
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
        self.assertTrue(host_state.__class__ is host_manager.HostState)
        self.assertEquals(host_state.service, {})

    def test_canonicalize_node(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             }
        dn = baremetal_host_manager._canonicalize_node(n)
        self.assertEqual(dn.get('id'), 1)
        self.assertEqual(dn.get('cpus'), 2)
        self.assertEqual(dn.get('memory_mb'), 3)
        self.assertEqual(dn.get('local_gb'), 4)
        self.assertTrue('instance_uuid' in dn)
        self.assertTrue(dn['instance_uuid'] is None)

    def test_canonicalize_node_with_instance_uuid(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             'instance_uuid': 'uuuuiidd'
             }
        dn = baremetal_host_manager._canonicalize_node(n)
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
        dn = baremetal_host_manager._canonicalize_node(n)
        self.assertTrue(dn is None)

    def test_canonicalize_node_registration_not_done(self):
        n = {'id': 1,
             'cpus': 2,
             'memory_mb': 3,
             'local_gb': 4,
             'registration_status': '!done',
             }
        dn = baremetal_host_manager._canonicalize_node(n)
        self.assertTrue(dn is None)

    def test_canonicalize_node_with_spec_none(self):
        n = {'id': 1,
             'local_gb': 4,
             }
        dn = baremetal_host_manager._canonicalize_node(n)
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

        self.assertEqual(i['A'], NODES_USED[0]['id'])
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
        self.assertTrue(s._nodes is None)
        self.assertTrue(s._instances is None)
        self.assertEqual(s.free_ram_mb, 0)
        self.assertEqual(s.free_disk_mb, 0)
        self.assertEqual(s.vcpus_total, 0)
        self.assertEqual(s.vcpus_used, 0)
        return s

    def test_update_from_compute_node(self):
        s = self.test_init()
        s.update_from_compute_node(None)
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
        s.update_from_compute_node(None)
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
        s = self.test_update_from_compute_node()
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
        s = self.test_update_from_compute_node()
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
        s = self.test_update_from_compute_node()
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


BAREMETAL_COMPUTE_NODES = [
        dict(id=1, service_id=1, local_gb=10240, memory_mb=10240, vcpus=10,
                service=dict(host='host1', disabled=True)),
        dict(id=2, service_id=2, local_gb=2048, memory_mb=1024, vcpus=2,
                service=dict(host='host2', disabled=True)),
        dict(id=3, service_id=3, local_gb=2048, memory_mb=2048, vcpus=2,
                service=dict(host='host3', disabled=True)),
        dict(id=4, service_id=4, local_gb=2048, memory_mb=2048, vcpus=7,
                service=dict(host='host4', disabled=False)),
        # Broken entry
        dict(id=5, service_id=5, local_gb=1024, memory_mb=1024, vcpus=1,
                service=None),
]


auto_id = 0


def id_dict(**kwargs):
    d = dict(**kwargs)
    if 'id' not in d:
        global auto_id
        auto_id += 1
        d['id'] = auto_id
    return d

BAREMETAL_INSTANCES = [
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                host='host1', uuid='1'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                host='host1', uuid='2'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=2,
                host='host2', uuid='3'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=3,
                host='host3', uuid='4'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=4,
                host='host4', uuid='5'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=2,
                host='host4', uuid='6'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                host='host2', uuid='7'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                host='host3', uuid='8'),
        dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                host='host1', uuid='9'),
        # Broken host
        dict(root_gb=1024, ephemeral_gb=0, memory_mb=1024, vcpus=1,
                host=None, uuid='1000'),
        # No matching host
        dict(root_gb=1024, ephemeral_gb=0, memory_mb=1024, vcpus=1,
                host='hostz', uuid='2000'),
]


BAREMETAL_NODES_1 = [
        id_dict(cpus=2, instance_uuid='9', ipmi_address='172.27.2.111',
                memory_mb=1024, local_gb=0),
        id_dict(cpus=3, instance_uuid='2', ipmi_address='172.27.2.111',
                memory_mb=4096, local_gb=0),
        id_dict(cpus=3, instance_uuid='1', ipmi_address='172.27.2.111',
                memory_mb=8192, local_gb=0),
        # No matching host
        id_dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=512, local_gb=0),
        id_dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=1024, local_gb=0),
        id_dict(cpus=2, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=2048, local_gb=0),
        id_dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=256, local_gb=0),
        id_dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.111',
                memory_mb=10240, local_gb=0),
]

BAREMETAL_NODES_2 = [
        id_dict(cpus=4, instance_uuid='3', ipmi_address='172.27.2.112',
                memory_mb=10240, local_gb=0),
        # No matching host
        id_dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=2048, local_gb=0),
        id_dict(cpus=3, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=2048, local_gb=0),
        id_dict(cpus=2, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=512, local_gb=0),
        id_dict(cpus=3, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=8192, local_gb=0),
        id_dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=1024, local_gb=0),
        id_dict(cpus=2, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=4096, local_gb=0),
        id_dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.112',
                memory_mb=512, local_gb=0),
]

BAREMETAL_NODES_3 = [
        id_dict(cpus=5, instance_uuid='4', ipmi_address='172.27.2.113',
                memory_mb=8192, local_gb=0),
        id_dict(cpus=4, instance_uuid='7', ipmi_address='172.27.2.113',
                memory_mb=10240, local_gb=0),
        # No matching host
        id_dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.113',
                memory_mb=512, local_gb=0),
        id_dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.113',
                memory_mb=2048, local_gb=0),
        id_dict(cpus=5, instance_uuid=None, ipmi_address='172.27.2.113',
                memory_mb=1024, local_gb=0),
        id_dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.113',
                memory_mb=512, local_gb=0),
]


BAREMETAL_NODES_4 = [
        id_dict(cpus=5, instance_uuid='5', ipmi_address='172.27.2.114',
                memory_mb=8192, local_gb=0),
        id_dict(cpus=6, instance_uuid='6', ipmi_address='172.27.2.114',
                memory_mb=8192, local_gb=0),
        # No matching host
        id_dict(cpus=5, instance_uuid=None, ipmi_address='172.27.2.114',
                memory_mb=512, local_gb=0),
        id_dict(cpus=6, instance_uuid=None, ipmi_address='172.27.2.114',
                memory_mb=512, local_gb=0),
        id_dict(cpus=1, instance_uuid=None, ipmi_address='172.27.2.114',
                memory_mb=512, local_gb=0),
        id_dict(cpus=4, instance_uuid=None, ipmi_address='172.27.2.114',
                memory_mb=10240, local_gb=0),
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
        self.bhm = baremetal_host_manager.BaremetalHostManager()

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
        fake_host1 = baremetal_host_manager.BaremetalHostState('host1', topic)
        fake_host2 = baremetal_host_manager.BaremetalHostState('host2', topic)
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

        context = 'fake_context'
        topic = 'compute'
        host = 'fakehost-1'
        self.mox.StubOutWithMock(db, 'compute_node_get_all')
        self.mox.StubOutWithMock(host_manager.LOG, 'warn')
        self.mox.StubOutWithMock(db, 'instance_get_all')
        self.stubs.Set(timeutils, 'utcnow', lambda: 31337)

        db.compute_node_get_all(context).AndReturn(BAREMETAL_COMPUTE_NODES)

        # Invalid service
        host_manager.LOG.warn("No service for compute ID 5")
        db.instance_get_all(context,
                columns_to_join=['instance_type']).\
                AndReturn(BAREMETAL_INSTANCES)
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

        num_bm_nodes = len(BAREMETAL_COMPUTE_NODES)

        # not contains broken entry
        self.assertEqual(len(host_states), num_bm_nodes - 1)
        self.assertIn('host1', host_states)
        self.assertIn('host2', host_states)
        self.assertIn('host3', host_states)
        self.assertIn('host4', host_states)

        # check returned value
        # host1 : subtract total ram of BAREMETAL_INSTANCES
        # from BAREMETAL_COMPUTE_NODES
        # host1 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host1'].vcpus_total, 4)
        self.assertEqual(host_states['host1'].free_ram_mb, 10240)

        # host2 : subtract BAREMETAL_INSTANCES from BAREMETAL_NODES_2
        # host2 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host2'].free_ram_mb, 8192)
        self.assertEqual(host_states['host2'].vcpus_total, 3)

        # host3 : subtract BAREMETAL_INSTANCES from BAREMETAL_NODES_3
        # host3 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host3'].free_ram_mb, 2048)
        self.assertEqual(host_states['host3'].vcpus_total, 4)

        # host4 : subtract BAREMETAL_INSTANCES from BAREMETAL_COMPUTE_NODES
        # host4 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host4'].free_ram_mb, 512)
        self.assertEqual(host_states['host4'].vcpus_used, 6)

        self.mox.VerifyAll()
