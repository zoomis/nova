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

from nova.scheduler import baremetal_utils
from nova.tests.baremetal.db import utils


FLAGS = flags.FLAGS


class FindNodeTestCase(test.TestCase):

    def test_find_suitable_node_for_memory(self):
        n1 = utils.new_bm_node(id=1, memory_mb=512)
        n2 = utils.new_bm_node(id=2, memory_mb=2048)
        n3 = utils.new_bm_node(id=3, memory_mb=1024)
        nodes = [n1, n2, n3]
        inst = {'vcpus': 1}

        inst['memory_mb'] = 1
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertEqual(result['id'], 1)

        inst['memory_mb'] = 512
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertEqual(result['id'], 1)

        inst['memory_mb'] = 513
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertEqual(result['id'], 3)

        inst['memory_mb'] = 1024
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertEqual(result['id'], 3)

        inst['memory_mb'] = 1025
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertEqual(result['id'], 2)

        inst['memory_mb'] = 2048
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertEqual(result['id'], 2)

        inst['memory_mb'] = 2049
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertTrue(result is None)

    def test_find_suitable_node_for_cpu(self):
        n1 = utils.new_bm_node(id=1, cpus=1, memory_mb=512)
        n2 = utils.new_bm_node(id=2, cpus=2, memory_mb=512)
        n3 = utils.new_bm_node(id=3, cpus=3, memory_mb=512)
        nodes = [n1, n2, n3]
        inst = {'memory_mb': 512}

        inst['vcpus'] = 1
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertEqual(result['id'], 1)

        inst['vcpus'] = 2
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertEqual(result['id'], 2)

        inst['vcpus'] = 3
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertEqual(result['id'], 3)

        inst['vcpus'] = 4
        result = baremetal_utils.find_suitable_node(inst, nodes)
        self.assertTrue(result is None)
