# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012, The SAVI Project.
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

__author__ = 'Hesam, Rahimi Koopayi (hesam.rahimikoopayi@utoronto.ca)'

"""
Class for booting-up BEE2 board, the SAVI reconfigurable hardware resource.
"""

import os
import shutil

from nova.compute import instance_types
from nova import exception
from nova import flags
from nova.openstack.common import log as logging
from nova import utils
from nova.virt.disk import api as disk
from nova.virt.libvirt import utils as libvirt_utils
from nova.virt.bee2.tcp_handler import tcp_handler


LOG = logging.getLogger(__name__)
FLAGS = flags.FLAGS

def get_baremetal_nodes():
    return BEE2()

def _cache_image_x(context, target, image_id,
                   user_id, project_id):
    if not os.path.exists(target):
        libvirt_utils.fetch_image(context, target, image_id,
                                  user_id, project_id)

class BEE2(object):

    def define_vars(self, instance, network_info, block_device_info):
        var = {}
        var['image_root'] = os.path.join(FLAGS.instances_path,
                                         instance['name'])
        var['network_info'] = network_info
        return var

    def create_image(self, var, context, image_meta, node, instance,
                     injected_files=None, admin_password=None):
        image_root = var['image_root']
        ami_id = str(image_meta['id'])
        utils.ensure_tree(image_root)
        image_path = os.path.join(image_root, 'disk')
        LOG.debug("fetching image id=%s target=%s", ami_id, image_path)
        _cache_image_x(context=context,
                       target=image_path,
                       image_id=ami_id,
                       user_id=instance['user_id'],
                       project_id=instance['project_id'])
        var['image_path'] = image_path
        LOG.debug("BEE2 bitfile is fetched successfully! fetching images all done.")

    def destroy_images(self, var, context, node, instance):
        LOG.debug("in destroy_image")
        image_root = var['image_root']
        shutil.rmtree(image_root, ignore_errors=True)
        LOG.debug("finished destroy_image")

    def _find_MAC_Addresses(self, network_info):
        nets = []
        ifc_num = -1
        for (network_ref, mapping) in network_info:
            ifc_num += 1
            name = 'eth%d' % ifc_num
            net_info = {'name': name,
                    'hwaddress': mapping['mac']}
            nets.append(net_info)
        return nets

    def _getfpga(self, image_path, node, nets):
        LOG.debug("Processing GET & PROGRAM command")
        try:
            result, message = tcp_handler("GET", 1, "", 9, node['pm_address'])
            result, message = tcp_handler("PRG", 1, "", 9, node['pm_address'], image_path)
            for index, item in enumerate(nets):
                result, message = tcp_handler("MAC", 1, item['hwaddress'], (index+1),node['pm_address'], image_path)
            LOG.debug("after processing tcp_handler:GET & PROGRAM $ SET-MAC commands")
        except:
            LOG.debug("TCP DIED")
            LOG.exception("failed to connect to the subAgent host")
	    raise exception.NovaException('TCP CONNETION DIED')
        else:
            if (result == "OK"):
                LOG.debug("FPGA-GOTTEN & FPGA-PROGRAMED")
            else:
                LOG.debug("FPGA-GET&PRG ERROR!")
        LOG.debug("FPGA-GET&PRG Finished")

    def _releasefpga(self, node):
        LOG.debug("Processing RELEASE command")
        try:
            result, message = tcp_handler("REL", 1, "", 9, node['pm_address'])
        except:
            LOG.debug("TCP DIED")
            LOG.exception("failed to connect to the subAgent host")
            raise exception.NovaException('TCP CONNETION DIED')
        else:
            if (result == "OK"):
                LOG.debug("FPGA-RELEASED")
            else:
                LOG.debug("FPGA-REL ERROR!")
        LOG.debug("FPGA-REL Finished")

    def activate_bootloader(self, var, context, node, instance):
        image_path = var['image_path']
        inst_type_id = instance['instance_type_id']
        inst_type = instance_types.get_instance_type(inst_type_id)
        network_info = var['network_info']
        nets = self._find_MAC_Addresses(network_info)
        self._getfpga(image_path, node, nets)
        LOG.debug("successfully bypassing activate_bootloader")

    def deactivate_bootloader(self, var, context, node, instance):
        self._releasefpga(node)
	LOG.debug("bypassing deactivate_bootloader")
	pass
    def activate_node(self, var, context, node, instance):
        pass

    def deactivate_node(self, var, context, node, instance):
        pass

