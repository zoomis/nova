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


BAREMETAL_NODES_X_FREE = [
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

BAREMETAL_NODES_X_USED = [
        dict(id=7, cpus=1, instance_uuid='A',
                memory_mb=512, local_gb=700),
        dict(id=8, cpus=4, instance_uuid='B',
                memory_mb=10240, local_gb=800),
]

BAREMETAL_NODES_X = []
BAREMETAL_NODES_X.extend(BAREMETAL_NODES_X_FREE)
BAREMETAL_NODES_X.extend(BAREMETAL_NODES_X_USED)

class BaremetalHostStateTestCase(test.TestCase):
    def test_baremetal_host(self):
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
        self.assertIs(host_state.__class__, baremetal_host_manager.BaremetalHostState)
        self.assertEquals(host_state.service, {})

    def test_vm_host(self):
        compute_caps = dict()
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

    def test_init(self):
        cap = {'timestamp': 1,
               'instance_type_extra_specs': {'baremetal_driver': 'test'},
               'nodes': BAREMETAL_NODES_X,
                }
        caps = {'compute': cap}
        s = baremetal_host_manager.new_host_state(
            None,
            "host2",
            "compute",
            capabilities=caps)
        self.assertEqual(s._nodes_from_capabilities, BAREMETAL_NODES_X)
        self.assertEqual(len(s._nodes), 6)
        self.assertEqual(len(s._instances), 2)
        self.assertEqual(s.free_ram_mb, 8192)
        self.assertEqual(s.free_disk_mb, 400 * 1024)
        self.assertEqual(s.vcpus_total, 3)
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
    
    def test_map_nodes(self):
        n, i = baremetal_host_manager._map_nodes(BAREMETAL_NODES_X)

        self.assertEqual(n[1], BAREMETAL_NODES_X_FREE[0])
        self.assertEqual(n[2], BAREMETAL_NODES_X_FREE[1])
        self.assertEqual(n[3], BAREMETAL_NODES_X_FREE[2])
        self.assertEqual(n[4], BAREMETAL_NODES_X_FREE[3])
        self.assertEqual(n[5], BAREMETAL_NODES_X_FREE[4])
        self.assertEqual(n[6], BAREMETAL_NODES_X_FREE[5])
        self.assertEqual(len(n), 6)

        self.assertEqual(i['A'], BAREMETAL_NODES_X_USED[0])
        self.assertEqual(i['B'], BAREMETAL_NODES_X_USED[1])
        self.assertEqual(len(i), 2)


class BaremetalHostManagerTestCase(test.TestCase):
    """Test case for HostManager class"""

    def setUp(self):
        super(BaremetalHostManagerTestCase, self).setUp()
        self.baremetal_host_manager =\
                baremetal_host_manager.BaremetalHostManager()

    def test_choose_host_filters_not_found(self):
        self.flags(scheduler_default_filters='ComputeFilterClass3')
        self.baremetal_host_manager.filter_classes = [ComputeFilterClass1,
                ComputeFilterClass2]
        self.assertRaises(exception.SchedulerHostFilterNotFound,
                self.baremetal_host_manager._choose_host_filters, None)

    def test_choose_host_filters(self):
        self.flags(scheduler_default_filters=['ComputeFilterClass2'])
        self.baremetal_host_manager.filter_classes = [ComputeFilterClass1,
                ComputeFilterClass2]

        # Test 'compute' returns 1 correct function
        filter_fns = self.baremetal_host_manager._choose_host_filters(None)
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

        self.mox.StubOutWithMock(self.baremetal_host_manager,
                '_choose_host_filters')
        self.mox.StubOutWithMock(fake_host1, 'passes_filters')
        self.mox.StubOutWithMock(fake_host2, 'passes_filters')

        self.baremetal_host_manager._choose_host_filters(None).\
                AndReturn(filters)
        fake_host1.passes_filters(filters, filter_properties).AndReturn(
                False)
        fake_host2.passes_filters(filters, filter_properties).AndReturn(
                True)

        self.mox.ReplayAll()
        filtered_hosts = self.baremetal_host_manager.filter_hosts(hosts,
                filter_properties, filters=None)
        self.assertEqual(len(filtered_hosts), 1)
        self.assertEqual(filtered_hosts[0], fake_host2)
        self.mox.VerifyAll()

    def test_update_service_capabilities(self):
        service_states = self.baremetal_host_manager.service_states
        self.assertDictMatch(service_states, {})
        self.mox.StubOutWithMock(timeutils, 'utcnow')
        timeutils.utcnow().AndReturn(31337)
        timeutils.utcnow().AndReturn(31338)
        timeutils.utcnow().AndReturn(31339)

        host1_compute_capabs = dict(free_memory=1234, host_memory=5678,
                timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'})
        host1_volume_capabs = dict(free_disk=4321, timestamp=1)
        host2_compute_capabs = dict(free_memory=8756, timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'})

        self.mox.ReplayAll()
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host1', host1_compute_capabs)
        self.baremetal_host_manager.update_service_capabilities('volume',
                'host1', host1_volume_capabs)
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host2', host2_compute_capabs)

        # Make sure dictionary isn't re-assigned
        self.assertEqual(self.baremetal_host_manager.service_states,
                service_states)
        # Make sure original dictionary wasn't copied
        self.assertEqual(host1_compute_capabs['timestamp'], 1)
        self.assertEqual(
            host1_compute_capabs['instance_type_extra_specs'][\
            'baremetal_driver'],
            'test')

        host1_compute_capabs['timestamp'] = 31337
        host1_volume_capabs['timestamp'] = 31338
        host2_compute_capabs['timestamp'] = 31339

        expected = {'host1': {'compute': host1_compute_capabs,
                              'volume': host1_volume_capabs},
                    'host2': {'compute': host2_compute_capabs}}
        self.assertDictMatch(service_states, expected)
        self.mox.VerifyAll()

    def test_get_all_host_states(self):
        self.flags(reserved_host_memory_mb=512,
                reserved_host_disk_mb=1024)

        context = 'fake_context'
        topic = 'compute'

        self.mox.StubOutWithMock(db, 'compute_node_get_all')
        self.mox.StubOutWithMock(host_manager.LOG, 'warn')
        self.mox.StubOutWithMock(db, 'instance_get_all')
        self.stubs.Set(timeutils, 'utcnow', lambda: 31337)

        def _fake_bm_node_get_all(context, service_host=None):
            if service_host == 'host1':
                return BAREMETAL_NODES_1
            elif service_host == 'host2':
                return BAREMETAL_NODES_2
            elif service_host == 'host3':
                return BAREMETAL_NODES_3
            elif service_host == 'host4':
                return BAREMETAL_NODES_4
            else:
                return {}

        def _fake_bm_node_get_by_instance_uuid(context, instance_uuid):
            return None

        self.stubs.Set(bmdb, 'bm_node_get_all', _fake_bm_node_get_all)
        self.stubs.Set(bmdb, 'bm_node_get_by_instance_uuid',
                _fake_bm_node_get_by_instance_uuid)

        db.compute_node_get_all(context).AndReturn(BAREMETAL_COMPUTE_NODES)

        # Invalid service
        host_manager.LOG.warn("No service for compute ID 5")
        db.instance_get_all(context,
                columns_to_join=['instance_type']).\
                AndReturn(BAREMETAL_INSTANCES)
        self.mox.ReplayAll()

        host1_compute_capabs = dict(free_memory=1234, host_memory=5678,
                timestamp=1)
        host2_compute_capabs = dict(free_memory=1234, host_memory=5678,
                timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'})
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host1', host1_compute_capabs)
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host2', host2_compute_capabs)
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host3', host2_compute_capabs)
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host4', host2_compute_capabs)

        host_states = self.baremetal_host_manager.get_all_host_states(context,
                topic)

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
        self.assertEqual(host_states['host1'].free_ram_mb +\
                FLAGS.reserved_host_memory_mb, 8704)
        self.assertEqual(host_states['host1'].vcpus_used, 5)

        # host2 : subtract BAREMETAL_INSTANCES from BAREMETAL_NODES_2
        # host2 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host2'].free_ram_mb, 8192)
        self.assertEqual(host_states['host2'].vcpus_total, 3)

        # host3 : subtract BAREMETAL_INSTANCES from BAREMETAL_NODES_3
        # host3 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host3'].free_ram_mb, 2048)
        self.assertEqual(host_states['host3'].vcpus_total, 4)

        # host4 : subtract BAREMETAL_INSTANCES from BAREMETAL_NODES_4
        # host4 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host4'].free_ram_mb, 8192)
        self.assertEqual(host_states['host4'].vcpus_total, 5)

        self.mox.VerifyAll()

    def test_get_all_host_states_2(self):
        self.flags(reserved_host_memory_mb=512,
                reserved_host_disk_mb=1024)

        context = 'fake_context'
        topic = 'compute'

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

        host1_compute_capabs = dict(free_memory=1234, host_memory=5678,
                timestamp=1)
        host2_compute_capabs = dict(
                timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'},
                nodes=BAREMETAL_NODES_2)
        host3_compute_capabs = dict(
                timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'},
                nodes=BAREMETAL_NODES_3)
        host4_compute_capabs = dict(
                timestamp=1,
                instance_type_extra_specs={'baremetal_driver': 'test'},
                nodes=BAREMETAL_NODES_4)
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host1', host1_compute_capabs)
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host2', host2_compute_capabs)
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host3', host3_compute_capabs)
        self.baremetal_host_manager.update_service_capabilities('compute',
                'host4', host4_compute_capabs)

        host_states = self.baremetal_host_manager.get_all_host_states(context,
                topic)
        print host_states

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
        self.assertEqual(host_states['host1'].free_ram_mb +\
                FLAGS.reserved_host_memory_mb, 8704)
        self.assertEqual(host_states['host1'].vcpus_used, 5)

        # host2 : subtract BAREMETAL_INSTANCES from BAREMETAL_NODES_2
        # host2 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host2'].free_ram_mb, 8192)
        self.assertEqual(host_states['host2'].vcpus_total, 3)

        # host3 : subtract BAREMETAL_INSTANCES from BAREMETAL_NODES_3
        # host3 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host3'].free_ram_mb, 2048)
        self.assertEqual(host_states['host3'].vcpus_total, 4)

        # host4 : subtract BAREMETAL_INSTANCES from BAREMETAL_NODES_4
        # host4 : total vcpu of BAREMETAL_INSTANCES
        self.assertEqual(host_states['host4'].free_ram_mb, 8192)
        self.assertEqual(host_states['host4'].vcpus_total, 5)

        self.mox.VerifyAll()
