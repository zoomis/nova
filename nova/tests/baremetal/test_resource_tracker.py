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
Tests for bare-metal resource tracker.
"""

import mox

from nova import flags
from nova import test
from nova.virt.baremetal import driver as bm_driver


FLAGS = flags.FLAGS


class BareMetalResourceTrackerTestCase(test.TestCase):
    def setUp(self):
        super(BareMetalResourceTrackerTestCase, self).setUp()
        self.rt = bm_driver.BareMetalResourceTracker(
                FLAGS.host, None, nodename='x')
        self.resources = {'memory_mb': 2048,
                          'memory_mb_used': 0,
                          'local_gb': 64,
                          'local_gb_used': 0,
                          }

    def test_consume(self):
        self.rt.apply_instance_to_resources(self.resources,
                                            instance=None,
                                            sign=1)
        self.assertEqual(self.resources['memory_mb_used'], 2048)
        self.assertEqual(self.resources['local_gb_used'], 64)

    def test_release(self):
        self.rt.apply_instance_to_resources(self.resources,
                                            instance=None,
                                            sign=-1)
        self.assertEqual(self.resources['memory_mb_used'], 0)
        self.assertEqual(self.resources['local_gb_used'], 0)
