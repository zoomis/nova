# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2012, The SAVI Project.
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

from webob import exc

from nova import exception
from nova import flags
from nova.openstack.common import log as logging

from nova.virt.baremetal import vif_driver

FLAGS = flags.FLAGS

LOG = logging.getLogger(__name__)

# For connecting with Ryu API
import httplib
from ryu.app.client import OFPClient
from nova.openstack.common import cfg

ryu_libvirt_ovs_driver_opt = cfg.StrOpt('libvirt_ovs_ryu_api_host',
                                        default='127.0.0.1:8080',
                                        help='Openflow Ryu REST API host:port')
FLAGS.register_opt(ryu_libvirt_ovs_driver_opt)

class RyuVIFDriver(vif_driver.BareMetalVIFDriver):
    def __init__(self, **kwargs):
        super(RyuVIFDriver, self).__init__()
        LOG.debug('ryu rest host %s', FLAGS.libvirt_ovs_ryu_api_host)
        self.ryu_client = OFPClient(FLAGS.libvirt_ovs_ryu_api_host)

    def _after_plug(self, instance, network, mapping, pif):
        dpid = pif['datapath_id']
        if dpid.find("0x") == 0:
            dpid = dpid[2:]

        # Register MAC with network first, then try to register port
        try:
            self.ryu_client.add_mac(network['id'], mapping['mac'])
            self.ryu_client.create_port(network['id'], dpid, pif['port_no'])
        except httplib.HTTPException as e:
            res = e.args[0]
            if res.status != httplib.CONFLICT:
                raise

    def _after_unplug(self, instance, network, mapping, pif):
        dpid = pif['datapath_id']
        if dpid.find("0x") == 0:
            dpid = dpid[2:]

        try:
            self.ryu_client.del_mac(network['id'], mapping['mac'])
            self.ryu_client.delete_port(network['id'], dpid, pif['port_no'])
        except httplib.HTTPException as e:
            res = e.args[0]
            if res.status != httplib.NOT_FOUND:
                raise

