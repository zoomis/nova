# Copyright (c) 2012 NTT DOCOMO, INC.
# Copyright (c) 2011 University of Southern California / ISI
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
Tests for baremetal connection.
"""

import mox

from nova import flags
from nova import test

from nova.tests.baremetal.db import utils
from nova.tests.image import fake as fake_image
from nova.tests import utils as test_utils
from nova.virt.baremetal import baremetal_states
from nova.virt.baremetal import db
from nova.virt.baremetal import driver as c
from nova.virt.baremetal import volume_driver
from nova.virt.firewall import NoopFirewallDriver


FLAGS = flags.FLAGS


class FakeVifDriver(object):

    def plug(self, instance, vif):
        pass

    def unplug(self, instance, vif):
        pass

FakeFirewallDriver = NoopFirewallDriver


class FakeVolumeDriver(volume_driver.VolumeDriver):
    def __init__(self):
        super(FakeVolumeDriver, self).__init__()
        self._initiator = "testtesttest"


NODE = utils.new_bm_node(cpus=2, memory_mb=4096, service_host="host1")
NICS = [
       {'address': '01:23:45:67:89:01', 'datapath_id': '0x1', 'port_no': 1, },
       {'address': '01:23:45:67:89:02', 'datapath_id': '0x2', 'port_no': 2, },
        ]


def class_path(class_):
    return class_.__module__ + '.' + class_.__name__


class BaremetalDriverTestCase(test.TestCase):

    def setUp(self):
        super(BaremetalDriverTestCase, self).setUp()
        self.flags(baremetal_sql_connection='sqlite:///:memory:',
                   host=NODE['service_host'],
                   baremetal_driver='nova.virt.baremetal.fake.Fake',
                   power_manager='nova.virt.baremetal.ipmi.DummyIpmi',
                   baremetal_vif_driver=class_path(FakeVifDriver),
                   baremetal_firewall_driver=class_path(FakeFirewallDriver),
                   baremetal_volume_driver=class_path(FakeVolumeDriver),
                   instance_type_extra_specs=['cpu_arch:test'],
                   )
        utils.clear_tables()
        context = test_utils.get_test_admin_context()
        node = db.bm_node_create(context, NODE)
        self.node_id = node['id']
        for nic in NICS:
            db.bm_interface_create(context,
                                      node['id'],
                                      nic['address'],
                                      nic['datapath_id'],
                                      nic['port_no'])
        fake_image.stub_out_image_service(self.stubs)

    def tearDown(self):
        super(BaremetalDriverTestCase, self).tearDown()

    def test_loading_baremetal_drivers(self):
        from nova.virt.baremetal import fake
        drv = c.BareMetalDriver()
        self.assertTrue(isinstance(drv.baremetal_nodes, fake.Fake))
        self.assertTrue(isinstance(drv._vif_driver, FakeVifDriver))
        self.assertTrue(isinstance(drv._firewall_driver, FakeFirewallDriver))
        self.assertTrue(isinstance(drv._volume_driver, FakeVolumeDriver))

    def test_spawn(self):
        context = test_utils.get_test_admin_context()
        instance = test_utils.get_test_instance()
        instance['uuid'] = '12345'
        network_info = test_utils.get_test_network_info()
        block_device_info = None
        image_meta = test_utils.get_test_image_info(None, instance)

        drv = c.BareMetalDriver()
        drv.spawn(context,
                  instance=instance,
                  image_meta=image_meta,
                  injected_files=[('/foo', 'bar'), ('/abc', 'xyz')],
                  admin_password='testpass',
                  network_info=network_info,
                  block_device_info=block_device_info)

        n = db.bm_node_get(context, self.node_id)
        self.assertEqual(n['instance_uuid'], instance['uuid'])
        self.assertEqual(n['task_state'], baremetal_states.ACTIVE)

    def test_get_host_stats(self):
        self.flags(instance_type_extra_specs=['cpu_arch:x86_64', 'x:123',
                                              'y:456', ])
        drv = c.BareMetalDriver()
        s = drv._get_host_stats()
        es = s['instance_type_extra_specs']
        self.assertEqual(es['cpu_arch'], 'x86_64')
        self.assertEqual(es['x'], '123')
        self.assertEqual(es['y'], '456')
        self.assertEqual(es['hypervisor_type'], 'baremetal')
        self.assertEqual(es['baremetal_driver'],
                         'nova.virt.baremetal.fake.Fake')
        self.assertEqual(len(es), 5)

    def test_max_sum_baremetal_resources(self):
        N1 = utils.new_bm_node(service_host="host1", cpus=1,
                                      memory_mb=1000, local_gb=10)
        N2 = utils.new_bm_node(service_host="host1", cpus=1,
                                      memory_mb=1000, local_gb=20)
        N3 = utils.new_bm_node(service_host="host1", cpus=10,
                                      memory_mb=1000, local_gb=20)
        N4 = utils.new_bm_node(service_host="host1", cpus=1,
                                      memory_mb=2000, local_gb=20)
        ns = [N1, N2, N3, N4, ]
        context = test_utils.get_test_admin_context()
        self.stubs.Set(c, '_get_baremetal_nodes', lambda ctx: ns)
        drv = c.BareMetalDriver()

        dic = drv._max_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 1)
        self.assertEqual(dic.get('memory_mb'), 2000)
        self.assertEqual(dic.get('local_gb'), 20)
        self.assertEqual(dic.get('vcpus_used'), 0)
        self.assertEqual(dic.get('memory_mb_used'), 0)
        self.assertEqual(dic.get('local_gb_used'), 0)
        dic = drv._sum_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 13)
        self.assertEqual(dic.get('memory_mb'), 5000)
        self.assertEqual(dic.get('local_gb'), 70)
        self.assertEqual(dic.get('vcpus_used'), 0)
        self.assertEqual(dic.get('memory_mb_used'), 0)
        self.assertEqual(dic.get('local_gb_used'), 0)

        N4['instance_uuid'] = '1'
        dic = drv._max_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 10)
        self.assertEqual(dic.get('memory_mb'), 1000)
        self.assertEqual(dic.get('local_gb'), 20)
        self.assertEqual(dic.get('vcpus_used'), 0)
        self.assertEqual(dic.get('memory_mb_used'), 0)
        self.assertEqual(dic.get('local_gb_used'), 0)
        dic = drv._sum_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 13)
        self.assertEqual(dic.get('memory_mb'), 5000)
        self.assertEqual(dic.get('local_gb'), 70)
        self.assertEqual(dic.get('vcpus_used'), 1)
        self.assertEqual(dic.get('memory_mb_used'), 2000)
        self.assertEqual(dic.get('local_gb_used'), 20)

        N3['instance_uuid'] = '2'
        dic = drv._max_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 1)
        self.assertEqual(dic.get('memory_mb'), 1000)
        self.assertEqual(dic.get('local_gb'), 20)
        self.assertEqual(dic.get('vcpus_used'), 0)
        self.assertEqual(dic.get('memory_mb_used'), 0)
        self.assertEqual(dic.get('local_gb_used'), 0)
        dic = drv._sum_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 13)
        self.assertEqual(dic.get('memory_mb'), 5000)
        self.assertEqual(dic.get('local_gb'), 70)
        self.assertEqual(dic.get('vcpus_used'), 11)
        self.assertEqual(dic.get('memory_mb_used'), 3000)
        self.assertEqual(dic.get('local_gb_used'), 40)

        N2['instance_uuid'] = '3'
        dic = drv._max_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 1)
        self.assertEqual(dic.get('memory_mb'), 1000)
        self.assertEqual(dic.get('local_gb'), 10)
        self.assertEqual(dic.get('vcpus_used'), 0)
        self.assertEqual(dic.get('memory_mb_used'), 0)
        self.assertEqual(dic.get('local_gb_used'), 0)
        dic = drv._sum_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 13)
        self.assertEqual(dic.get('memory_mb'), 5000)
        self.assertEqual(dic.get('local_gb'), 70)
        self.assertEqual(dic.get('vcpus_used'), 12)
        self.assertEqual(dic.get('memory_mb_used'), 4000)
        self.assertEqual(dic.get('local_gb_used'), 60)

        N1['instance_uuid'] = '4'
        dic = drv._max_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 0)
        self.assertEqual(dic.get('memory_mb'), 0)
        self.assertEqual(dic.get('local_gb'), 0)
        self.assertEqual(dic.get('vcpus_used'), 0)
        self.assertEqual(dic.get('memory_mb_used'), 0)
        self.assertEqual(dic.get('local_gb_used'), 0)
        dic = drv._sum_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 13)
        self.assertEqual(dic.get('memory_mb'), 5000)
        self.assertEqual(dic.get('local_gb'), 70)
        self.assertEqual(dic.get('vcpus_used'), 13)
        self.assertEqual(dic.get('memory_mb_used'), 5000)
        self.assertEqual(dic.get('local_gb_used'), 70)

        N2['instance_uuid'] = None
        dic = drv._max_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 1)
        self.assertEqual(dic.get('memory_mb'), 1000)
        self.assertEqual(dic.get('local_gb'), 20)
        self.assertEqual(dic.get('vcpus_used'), 0)
        self.assertEqual(dic.get('memory_mb_used'), 0)
        self.assertEqual(dic.get('local_gb_used'), 0)
        dic = drv._sum_baremetal_resources(context)
        self.assertEqual(dic.get('vcpus'), 13)
        self.assertEqual(dic.get('memory_mb'), 5000)
        self.assertEqual(dic.get('local_gb'), 70)
        self.assertEqual(dic.get('vcpus_used'), 12)
        self.assertEqual(dic.get('memory_mb_used'), 4000)
        self.assertEqual(dic.get('local_gb_used'), 50)
