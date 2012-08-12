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

import operator

from nova import context as ctx
from nova import db
from nova import flags
from nova.openstack.common import log as logging
from nova.scheduler import filters
from nova.scheduler import host_manager
from nova.virt.baremetal import bmdb


FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)


class BaremetalHostState(host_manager.HostState):
    """Mutable and immutable information tracked for a host.
    This is an attempt to remove the ad-hoc data structures
    previously used and lock down access.
    """

    def __init__(self, host, topic, capabilities=None, service=None):
        self.host = host
        self.topic = topic

        # Read-only capability dicts

        if capabilities is None:
            capabilities = {}
        self.capabilities = host_manager.ReadOnlyDict(capabilities.get(topic,
                                                                       None))

        self.baremetal_compute = False
        cap_extra_specs = self.capabilities.get('instance_type_extra_specs',
                                                {})
        if cap_extra_specs.get('baremetal_driver'):
            self.baremetal_compute = True

        if service is None:
            service = {}
        self.service = host_manager.ReadOnlyDict(service)
        # Mutable available resources.
        # These will change as resources are virtually "consumed".
        self.free_ram_mb = 0
        self.free_disk_mb = 0
        self.vcpus_total = 0
        self.vcpus_used = 0

        self.available_nodes = []

    def update_from_compute_node(self, compute, context=None):
        """Update information about a host from its compute_node info."""
        if self.baremetal_compute:
            service_host = compute['service']['host']
            bm_nodes = bmdb.bm_node_get_all(context,
                                            service_host=service_host)
            for n in bm_nodes:
                if not n['instance_uuid']:
                    self.available_nodes.append(n)

            """those sorting should be decided by weight in a scheduler."""
            self.available_nodes = sorted(self.available_nodes,
                                          key=operator.itemgetter('memory_mb'),
                                          reverse=True)
            self.available_nodes = sorted(self.available_nodes,
                                          key=operator.itemgetter('cpus'),
                                          reverse=True)

            if len(self.available_nodes):
                bm_node = self.available_nodes[0]
            else:
                bm_node = {}
                bm_node['local_gb'] = 0
                bm_node['memory_mb'] = 0
                bm_node['cpus'] = 0

            all_disk_mb = bm_node['local_gb'] * 1024
            all_ram_mb = bm_node['memory_mb']
            vcpus_total = bm_node['cpus']
        else:
            all_disk_mb = compute['local_gb'] * 1024
            all_ram_mb = compute['memory_mb']
            vcpus_total = compute['vcpus']
            if FLAGS.reserved_host_disk_mb > 0:
                all_disk_mb -= FLAGS.reserved_host_disk_mb
            if FLAGS.reserved_host_memory_mb > 0:
                all_ram_mb -= FLAGS.reserved_host_memory_mb

        self.free_ram_mb = all_ram_mb
        self.total_usable_ram_mb = all_ram_mb
        self.free_disk_mb = all_disk_mb
        self.vcpus_total = vcpus_total

    def consume_from_instance(self, instance):
        """Update information about a host from instance info."""
        if self.baremetal_compute:
            context = ctx.get_admin_context()
            instance_uuid = instance.get('uuid', None)
            if instance_uuid:
                bm_node = bmdb.bm_node_get_by_instance_uuid(context,
                                                            instance['uuid'])
            else:
                bm_node = None

            if bm_node:
                return

            if len(self.available_nodes):
                self.available_nodes.pop(0)

            if len(self.available_nodes):
                bm_node = self.available_nodes[0]
            else:
                bm_node = {}
                bm_node['local_gb'] = 0
                bm_node['memory_mb'] = 0
                bm_node['cpus'] = 0

            self.free_disk_mb = bm_node['local_gb'] * 1024
            self.free_ram_mb = bm_node['memory_mb']
            self.vcpus_used = 0
            self.vcpus_total = bm_node['cpus']
        else:
            disk_mb = (instance['root_gb'] + instance['ephemeral_gb']) * 1024
            ram_mb = instance['memory_mb']
            vcpus = instance['vcpus']
            self.free_ram_mb -= ram_mb
            self.free_disk_mb -= disk_mb
            self.vcpus_used += vcpus


class BaremetalHostManager(host_manager.HostManager):
    """Bare-Metal HostManager class."""

    # Can be overriden in a subclass
    host_state_cls = BaremetalHostState

    def __init__(self):
        self.service_states = {}  # { <host> : { <service> : { cap k : v }}}
        self.filter_classes = filters.get_filter_classes(
                FLAGS.scheduler_available_filters)

    def get_all_host_states(self, context, topic):
        """Returns a dict of all the hosts the HostManager
        knows about. Also, each of the consumable resources in HostState
        are pre-populated and adjusted based on data in the db.

        For example:
        {'192.168.1.100': HostState(), ...}

        Note: this can be very slow with a lot of instances.
        InstanceType table isn't required since a copy is stored
        with the instance (in case the InstanceType changed since the
        instance was created)."""

        if topic != 'compute':
            raise NotImplementedError(_(
                "host_manager only implemented for 'compute'"))

        host_state_map = {}

        # Make a compute node dict with the bare essential metrics.
        compute_nodes = db.compute_node_get_all(context)
        for compute in compute_nodes:
            service = compute['service']
            if not service:
                LOG.warn(_("No service for compute ID %s") % compute['id'])
                continue
            host = service['host']
            capabilities = self.service_states.get(host, None)
            host_state = self.host_state_cls(host, topic,
                    capabilities=capabilities,
                    service=dict(service.iteritems()))
            # pass context to access DB
            host_state.update_from_compute_node(compute, context=context)
            host_state_map[host] = host_state

        # "Consume" resources from the host the instance resides on.
        instances = db.instance_get_all(context,
                columns_to_join=['instance_type'])
        for instance in instances:
            host = instance['host']
            if not host:
                continue
            host_state = host_state_map.get(host, None)
            if not host_state:
                continue
            host_state.consume_from_instance(instance)
        return host_state_map
