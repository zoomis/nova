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
The FilterScheduler is for creating instances locally.
You can customize this scheduler by specifying your own Host Filters and
Weighing Functions.
"""

import operator

from nova import exception
from nova import flags
from nova.openstack.common import importutils
from nova.openstack.common import log as logging
from nova.openstack.common.notifier import api as notifier
from nova.scheduler import driver
from nova.scheduler import least_cost
from nova.scheduler import scheduler_options
from nova.scheduler.plugins import janus_plugin


FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)


class FilterScheduler(driver.Scheduler):
    """Scheduler that can be used for filtering and weighing."""
    def __init__(self, *args, **kwargs):
        super(FilterScheduler, self).__init__(*args, **kwargs)
        self.cost_function_cache = {}
        self.options = scheduler_options.SchedulerOptions()

    def schedule_create_volume(self, context, volume_id, snapshot_id, image_id,
                               reservations):
        # NOTE: We're only focused on compute instances right now,
        # so this method will always raise NoValidHost().
        msg = _("No host selection for %s defined.") % FLAGS.volume_topic
        raise exception.NoValidHost(reason=msg)

    def schedule_run_instance(self, context, request_spec,
                              admin_password, injected_files,
                              requested_networks, is_first_time,
                              filter_properties):
        """This method is called from nova.compute.api to provision
        an instance.  We first create a build plan (a list of WeightedHosts)
        and then provision.

        Returns a list of the instances created.
        """
        elevated = context.elevated()
        instance_uuids = request_spec.get('instance_uuids')
        num_instances = len(instance_uuids)
        LOG.debug(_("Attempting to build %(num_instances)d instance(s)") %
                locals())

        payload = dict(request_spec=request_spec)
        notifier.notify(context, notifier.publisher_id("scheduler"),
                        'scheduler.run_instance.start', notifier.INFO, payload)

        weighted_hosts = self._schedule(context, "compute", request_spec,
                                        filter_properties, instance_uuids)

        # NOTE(comstud): Make sure we do not pass this through.  It
        # contains an instance of RpcContext that cannot be serialized.
        filter_properties.pop('context', None)

        for num, instance_uuid in enumerate(instance_uuids):
            request_spec['instance_properties']['launch_index'] = num

            try:
                try:
                    weighted_host = weighted_hosts.pop(0)
                except IndexError:
                    raise exception.NoValidHost(reason="")

                self._provision_resource(elevated, weighted_host,
                                         request_spec,
                                         filter_properties,
                                         requested_networks,
                                         injected_files, admin_password,
                                         is_first_time,
                                         instance_uuid=instance_uuid)
            except Exception as ex:
                # NOTE(vish): we don't reraise the exception here to make sure
                #             that all instances in the request get set to
                #             error properly
                driver.handle_schedule_error(context, ex, instance_uuid,
                                             request_spec)
            # scrub retry host list in case we're scheduling multiple
            # instances:
            retry = filter_properties.get('retry', {})
            retry['hosts'] = []

        notifier.notify(context, notifier.publisher_id("scheduler"),
                        'scheduler.run_instance.end', notifier.INFO, payload)

    def schedule_prep_resize(self, context, image, request_spec,
                             filter_properties, instance, instance_type,
                             reservations):
        """Select a target for resize.

        Selects a target host for the instance, post-resize, and casts
        the prep_resize operation to it.
        """

        hosts = self._schedule(context, 'compute', request_spec,
                               filter_properties, [instance['uuid']])
        if not hosts:
            raise exception.NoValidHost(reason="")
        host = hosts.pop(0)

        # Forward off to the host
        self.compute_rpcapi.prep_resize(context, image, instance,
                instance_type, host.host_state.host, reservations)

    def _provision_resource(self, context, weighted_host, request_spec,
            filter_properties, requested_networks, injected_files,
            admin_password, is_first_time, instance_uuid=None):
        """Create the requested resource in this Zone."""
        # Add a retry entry for the selected compute host:
        self._add_retry_host(filter_properties, weighted_host.host_state.host)

        self._add_oversubscription_policy(filter_properties,
                weighted_host.host_state)

        payload = dict(request_spec=request_spec,
                       weighted_host=weighted_host.to_dict(),
                       instance_id=instance_uuid)
        notifier.notify(context, notifier.publisher_id("scheduler"),
                        'scheduler.run_instance.scheduled', notifier.INFO,
                        payload)

        updated_instance = driver.instance_update_db(context,
                instance_uuid, weighted_host.host_state.host)

        self.compute_rpcapi.run_instance(context, instance=updated_instance,
                host=weighted_host.host_state.host,
                request_spec=request_spec, filter_properties=filter_properties,
                requested_networks=requested_networks,
                injected_files=injected_files,
                admin_password=admin_password, is_first_time=is_first_time)

    def _add_retry_host(self, filter_properties, host):
        """Add a retry entry for the selected compute host.  In the event that
        the request gets re-scheduled, this entry will signal that the given
        host has already been tried.
        """
        retry = filter_properties.get('retry', None)
        if not retry:
            return
        hosts = retry['hosts']
        hosts.append(host)

    def _add_oversubscription_policy(self, filter_properties, host_state):
        filter_properties['limits'] = host_state.limits

    def _get_configuration_options(self):
        """Fetch options dictionary. Broken out for testing."""
        return self.options.get_configuration()

    def populate_filter_properties(self, request_spec, filter_properties):
        """Stuff things into filter_properties.  Can be overridden in a
        subclass to add more data.
        """
        pass

    def _max_attempts(self):
        max_attempts = FLAGS.scheduler_max_attempts
        if max_attempts < 1:
            raise exception.NovaException(_("Invalid value for "
                "'scheduler_max_attempts', must be >= 1"))
        return max_attempts

    def _populate_retry(self, filter_properties, instance_properties):
        """Populate filter properties with history of retries for this
        request. If maximum retries is exceeded, raise NoValidHost.
        """
        max_attempts = self._max_attempts()
        retry = filter_properties.pop('retry', {})

        if max_attempts == 1:
            # re-scheduling is disabled.
            return

        # retry is enabled, update attempt count:
        if retry:
            retry['num_attempts'] += 1
        else:
            retry = {
                'num_attempts': 1,
                'hosts': []  # list of compute hosts tried
            }
        filter_properties['retry'] = retry

        if retry['num_attempts'] > max_attempts:
            instance_uuid = instance_properties.get('uuid')
            msg = _("Exceeded max scheduling attempts %(max_attempts)d for "
                    "instance %(instance_uuid)s") % locals()
            raise exception.NoValidHost(reason=msg)

    def _schedule(self, context, topic, request_spec, filter_properties,
                  instance_uuids=None):
        """Returns a list of hosts that meet the required specs,
        ordered by their fitness.
        """
        elevated = context.elevated()
        if topic != "compute":
            msg = _("Scheduler only understands Compute nodes (for now)")
            raise NotImplementedError(msg)

        instance_properties = request_spec['instance_properties']
        instance_type = request_spec.get("instance_type", None)

        cost_functions = self.get_cost_functions()
        config_options = self._get_configuration_options()

        # check retry policy.  Rather ugly use of instance_uuids[0]...
        # but if we've exceeded max retries... then we really only
        # have a single instance.
        properties = instance_properties.copy()
        if instance_uuids:
            properties['uuid'] = instance_uuids[0]
        self._populate_retry(filter_properties, properties)

        filter_properties.update({'context': context,
                                  'request_spec': request_spec,
                                  'config_options': config_options,
                                  'instance_type': instance_type})

        self.populate_filter_properties(request_spec,
                                        filter_properties)

        # Find our local list of acceptable hosts by repeatedly
        # filtering and weighing our options. Each time we choose a
        # host, we virtually consume resources on it so subsequent
        # selections can adjust accordingly.

        # unfiltered_hosts_dict is {host : ZoneManager.HostInfo()}
        unfiltered_hosts_dict = self.host_manager.get_all_host_states(
                elevated, topic)

        # -------------------------------------------------------------------------------
        # @author Eliot J. Kang <eliot@savinetwork.ca>
        # Get hosts based on plugins
        # remove all hosts from unfiltered_hosts_dict which are not in plugined_hosts
        plugined_hosts = self.host_manager.get_plugined_hosts(elevated, topic, 
                                                              janus_plugin.JanusPlugin())
        LOG.debug(_("Host list before plugin: %s") % unfiltered_hosts_dict)
        for key in unfiltered_hosts_dict.keys():
            if not key in plugined_hosts:
                del unfiltered_hosts_dict[key]
        LOG.debug(_("Host list after plugin: %s") % unfiltered_hosts_dict)
        # -------------------------------------------------------------------------------

        # Note: remember, we are using an iterator here. So only
        # traverse this list once. This can bite you if the hosts
        # are being scanned in a filter or weighing function.
        hosts = unfiltered_hosts_dict.itervalues()

        selected_hosts = []
        if instance_uuids:
            num_instances = len(instance_uuids)
        else:
            num_instances = request_spec.get('num_instances', 1)
        for num in xrange(num_instances):
            # Select hosts based on Plugins
            
            # Filter local hosts based on requirements ...
            hosts = self.host_manager.filter_hosts(hosts,
                    filter_properties)
            if not hosts:
                # Can't get any more locally.
                break

            LOG.debug(_("Filtered %(hosts)s") % locals())

            # weighted_host = WeightedHost() ... the best
            # host for the job.
            # TODO(comstud): filter_properties will also be used for
            # weighing and I plan fold weighing into the host manager
            # in a future patch.  I'll address the naming of this
            # variable at that time.
            weighted_host = least_cost.weighted_sum(cost_functions,
                    hosts, filter_properties)
            LOG.debug(_("Weighted %(weighted_host)s") % locals())
            selected_hosts.append(weighted_host)

            # Now consume the resources so the filter/weights
            # will change for the next instance.
            weighted_host.host_state.consume_from_instance(
                    instance_properties)

        selected_hosts.sort(key=operator.attrgetter('weight'))
        return selected_hosts

    def get_cost_functions(self, topic=None):
        """Returns a list of tuples containing weights and cost functions to
        use for weighing hosts
        """
        if topic is None:
            # Schedulers only support compute right now.
            topic = "compute"
        if topic in self.cost_function_cache:
            return self.cost_function_cache[topic]

        cost_fns = []
        for cost_fn_str in FLAGS.least_cost_functions:
            if '.' in cost_fn_str:
                short_name = cost_fn_str.split('.')[-1]
            else:
                short_name = cost_fn_str
                cost_fn_str = "%s.%s.%s" % (
                        __name__, self.__class__.__name__, short_name)
            if not (short_name.startswith('%s_' % topic) or
                    short_name.startswith('noop')):
                continue

            try:
                # NOTE: import_class is somewhat misnamed since
                # the weighing function can be any non-class callable
                # (i.e., no 'self')
                cost_fn = importutils.import_class(cost_fn_str)
            except ImportError:
                raise exception.SchedulerCostFunctionNotFound(
                        cost_fn_str=cost_fn_str)

            try:
                flag_name = "%s_weight" % cost_fn.__name__
                weight = getattr(FLAGS, flag_name)
            except AttributeError:
                raise exception.SchedulerWeightFlagNotFound(
                        flag_name=flag_name)
            cost_fns.append((weight, cost_fn))

        self.cost_function_cache[topic] = cost_fns
        return cost_fns
