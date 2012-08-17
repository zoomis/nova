# Copyright (c) 2012 NTT DOCOMO, INC.
# Copyright (c) 2011 OpenStack, LLC.
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
Manage hosts in the current zone.
"""

from nova import flags
from nova.openstack.common import log as logging
from nova.scheduler import baremetal_utils
from nova.scheduler import host_manager


FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)


def _canonicalize_node(node):
    canon = {}
    if not node.get('id'):
        LOG.warn('Node has no id. This node is ignored in scheduling.')
        return None
    if node.get('registration_status', 'done') != 'done':
        return None
    canon['id'] = node['id']
    for k in ('memory_mb', 'cpus', 'local_gb'):
        canon[k] = node.get(k, 0)
    canon['instance_uuid'] = node.get('instance_uuid')
    return canon


def _map_nodes(nodes):
    nodes_map = {}
    instances = {}
    for n in nodes:
        n = _canonicalize_node(n)
        if n is None:
            continue
        if n['instance_uuid']:
            instances[n['instance_uuid']] = n
            continue
        if not baremetal_utils._is_available_node(n):
            continue
        nodes_map[n['id']] = n
    return (nodes_map, instances)


class BaremetalHostState(host_manager.HostState):
    """Mutable and immutable information tracked for a host.
    This is an attempt to remove the ad-hoc data structures
    previously used and lock down access.
    """

    def __init__(self, host, topic, capabilities=None, service=None):
        super(BaremetalHostState, self).__init__(host, topic, capabilities,
                                                 service)
        if capabilities is None:
            capabilities = {}
        cap = capabilities.get(topic, {})
        self._nodes_from_capabilities = cap.get('nodes', [])
        self._nodes = None
        self._instances = None
        self._init_nodes()

    def _init_nodes(self):
        nodes, instances = _map_nodes(self._nodes_from_capabilities)
        self._nodes = nodes
        self._instances = instances
        self._update()

    def _update(self):
        bm_node = baremetal_utils.find_biggest_node(self._nodes.values())
        if not bm_node:
            bm_node = {}
            bm_node['local_gb'] = 0
            bm_node['memory_mb'] = 0
            bm_node['cpus'] = 0
        self.free_ram_mb = bm_node['memory_mb']
        self.total_usable_ram_mb = bm_node['memory_mb']
        self.free_disk_mb = bm_node['local_gb'] * 1024
        self.vcpus_total = bm_node['cpus']

    def update_from_compute_node(self, compute):
        # Update(==initialize) information using capabilities.
        # compute_node info is not used.
        self._init_nodes()

    def consume_from_instance(self, instance):
        instance_uuid = instance.get('uuid', None)
        if instance_uuid:
            if instance_uuid in self._instances:
                return
        node = baremetal_utils.find_suitable_node(instance,
                                                  self._nodes.values())
        if not node:
            return
        self._nodes.pop(node['id'])
        if instance_uuid:
            self._instances[instance_uuid] = node
        self._update()


def new_host_state(self, host, topic, capabilities=None, service=None):
    """Returns an instance of BaremetalHostState or HostState according to
    capabilities. If 'baremetal_driver' is in capabilities, it returns an
    instance of BaremetalHostState. If not, returns an instance of HostState.
    """
    if capabilities is None:
        capabilities = {}
    cap = capabilities.get(topic, {})
    cap_extra_specs = cap.get('instance_type_extra_specs', {})
    if bool(cap_extra_specs.get('baremetal_driver')):
        return BaremetalHostState(host, topic, capabilities, service)
    else:
        return host_manager.HostState(host, topic, capabilities, service)


class BaremetalHostManager(host_manager.HostManager):
    """Bare-Metal HostManager class."""

    # Override.
    # Yes, this is not a class, and it is OK
    host_state_cls = new_host_state

    def __init__(self):
        super(BaremetalHostManager, self).__init__()
