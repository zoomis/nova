# vim: tabstop=4 shiftwidth=4 softtabstop=4
# coding=utf-8
#
# Copyright (c) 2012 NTT DOCOMO, INC
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
Utilities for bare-metal node selection
"""

from nova import flags
from nova.openstack.common import log as logging

FLAGS = flags.FLAGS

LOG = logging.getLogger(__name__)


def _is_available_node(node):
    if node.get('instance_uuid'):
        return False
    if node.get('registration_status', 'done') != 'done':
        return False
    return True


def _compare_node(n, m):
    for k in ('memory_mb', 'cpus', 'local_gb'):
        r = n[k] - m[k]
        if r != 0:
            return r
    return 0


def find_suitable_node(instance, nodes):
    def n0(v):
        if v is None:
            return 0
        return v
    instance_local_gb = n0(instance.get('root_gb')) \
                        + n0(instance.get('ephemeral_gb'))
    result = None
    for node in nodes:
        if not _is_available_node(node):
            continue
        if node['cpus'] < instance['vcpus']:
            continue
        if node['memory_mb'] < instance['memory_mb']:
            continue
        if node['local_gb'] < instance_local_gb:
            continue

        if result == None:
            result = node
        else:
            if _compare_node(node, result) < 0:
                result = node
    return result


def find_biggest_node(nodes):
    result = {'cpus': 0,
              'memory_mb': 0,
              'local_gb': 0,
              }
    for node in nodes:
        if not _is_available_node(node):
            continue
        if _compare_node(node, result) > 0:
            result = node
    return result
