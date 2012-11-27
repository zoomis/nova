# vim: tabstop=4 shiftwidth=4 softtabstop=4
# coding=utf-8

# Copyright (c) 2012 NTT DOCOMO, INC.
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
Class for Net Boot power manager.
"""

import os
import stat
import tempfile
import time

from nova import flags
from nova.openstack.common import cfg
from nova.openstack.common import log as logging
from nova import utils
from nova.virt.baremetal import baremetal_states

opts = [
    cfg.StrOpt('baremetal_term',
               default='shellinaboxd',
               help='path to baremetal terminal program'),
    cfg.StrOpt('baremetal_term_cert_dir',
               default=None,
               help='path to baremetal terminal SSL cert(PEM)'),
    cfg.StrOpt('baremetal_term_pid_dir',
               default='/var/lib/nova/baremetal/console',
               help='path to directory stores pidfiles of baremetal_term'),
    ]

FLAGS = flags.FLAGS
FLAGS.register_opts(opts)

LOG = logging.getLogger(__name__)


class SnmpNetBootError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.msg = message

    def __str__(self):
        return "%s: %s" % (self.status, self.msg)
#pm_user has the oids and type of bm
#type,oid_s[..]

class SnmpTypeB(object):

    def __init__(self, address, community, oids):
        self._address = address
        self._community = community
        self._oids = oids
        self._oid_s_p = oids[0]
        self._oid_s_r = oids[1]
        self._oid_g = oids[2]

    def _exec_snmpget_tool(self, oid):
        args = []
        args.append("snmpget")
        args.append("-t")
        args.append("15")
        args.append("-v1")
        args.append("-c"+self._community)
        args.append(self._address)
        args.append(oid)
        #print args
        LOG.debug("A:snmpget commands: %s", args)
        out, err = utils.execute(*args, attempts=3)
        LOG.debug("out: %s", out)
        LOG.debug("err: %s", err)
        return out, err

    def _exec_snmpset_tool(self, oid, command):
        args = []
        args.append("snmpset")
        args.append("-t")
        args.append("15")
        args.append("-v1")
        args.append("-c"+self._community)
        args.append(self._address)
        args.append(oid)
        args.extend(command.split(" "))
        LOG.debug("A:snmpset commands: %s", args)
        out, err = utils.execute(*args, attempts=3)
        LOG.debug("out: %s", out)
        LOG.debug("err: %s", err)
        return out, err

    def power_on(self):
        self._exec_snmpset_tool(self._oid_s_p, "i 1")

    def power_off(self):
        self._exec_snmpset_tool(self._oid_s_p, "i 0")

    def reboot(self):
        self._exec_snmpset_tool(self._oid_s_r, "i 1")

    def power_status(self):
        out_err = self._exec_snmpget_tool(self._oid_g)
        if out_err[1]=="":
           if out_err[0].endswith("1\n"):
              out_err = ("1\n", "")
           elif out_err[0].endswith("0\n"):
              out_err = ("2\n", "")
        return out_err 

class SnmpTypeA(object):

    def __init__(self, address, community, oids):
        self._address = address
        self._community = community
        self._oids = oids
        self._oid_s = oids[0]
        self._oid_g = oids[1]

    def _exec_snmpget_tool(self, command):
        args = []
        args.append("snmpget")
        args.append("-v2c")
        args.append("-c"+self._community)
        args.append(self._address)
        args.append(self._oid_g)
        LOG.debug("A:snmpget commands: %s", args)
        print args
        out, err = utils.execute(*args, attempts=3)
        LOG.debug("out: %s", out)
        LOG.debug("err: %s", err)
        return out, err

    def _exec_snmpset_tool(self, command):
        args = []
        args.append("snmpset")
        args.append("-v2c")
        args.append("-c"+self._community)
        args.append(self._address)
        args.append(self._oid_s)
        args.extend(command.split(" "))
        LOG.debug("A:snmpset commands: %s", args)
        print args
        out, err = utils.execute(*args, attempts=3)
        LOG.debug("out: %s", out)
        LOG.debug("err: %s", err)
        return out, err

    def power_on(self):
        self._exec_snmpset_tool("i 1")

    def power_off(self):
        self._exec_snmpset_tool("i 2")

    def reboot(self):
        self._exec_snmpset_tool("i 3")

    def power_status(self):
        out_err = self._exec_snmpget_tool("")
        return out_err       

class SnmpNetBoot(object):

    def __init__(self, node):
        self._address = node['pm_address']
        oids = node['pm_user'].split(",")
        self._type = oids[0]
        self._oids = oids[1:]
        self._community = node['pm_password']
        self._interface = "lanplus"
        self.power_state = False
        if self._address == None:
            raise SnmpNetBootError(-1, "address is None")
        if self._type == "a":
           if len(self._oids) < 2:
              raise SnmpNetBootError(-1, "snmp oid for type a is not enough")
        elif self._type == "b":
           if len(self._oids) < 3:
              raise SnmpNetBootError(-1, "snmp oid for type b is not enough")
        if self._community == None:
            raise SnmpNetBootError(-1, "snmp community(password) is None")
        if self._type == "a":
           self._snmp = SnmpTypeA(self._address, self._community, self._oids)
        elif self._type == "b":
           self._snmp = SnmpTypeB(self._address, self._community, self._oids)

    def _exec_snmpget_tool(self, command):
        args = []
        args.append("snmpget")
        args.append("-v2c")
        args.append("-c"+self._community)
        args.append(self._address)
        args.append(self._oid_g)
#       args.extend(command.split(" "))
        LOG.debug("snmpget commands: %s", args)
        out, err = utils.execute(*args, attempts=3)
        LOG.debug("out: %s", out)
        LOG.debug("err: %s", err)
        return out, err

    def _exec_snmpset_tool(self, command):
        args = []
        args.append("snmpset")
        args.append("-v2c")
        args.append("-c"+self._community)
        args.append(self._address)
        args.append(self._oid_s)
        args.extend(command.split(" "))
        LOG.debug("snmpset commands: %s", args)
        out, err = utils.execute(*args, attempts=3)
        LOG.debug("out: %s", out)
        LOG.debug("err: %s", err)
        return out, err

    def activate_node(self):
        LOG.debug("in activate node")
        state = self._power_on()
        state = baremetal_states.ACTIVE
        self.power_state = True
        return state

    def reboot_node(self):
        state = self._reboot()
        LOG.debug("in reboot node")
        state = baremetal_states.ACTIVE
        self.power_state = True
        return state

    def deactivate_node(self):
        state = self._power_off()
        LOG.debug("in deactivate node")
        state = baremetal_states.DELETED
        self.power_state = False
        return state

    def _power_on(self):
        count = 0
        while not self.is_power_on():
            count += 1
            if count > 3:
                return baremetal_states.ERROR
            try:
                self._snmp.power_on()
                #self._exec_snmpset_tool("i 1")
            except Exception:
                LOG.exception("power_on failed")
            time.sleep(5)
        return baremetal_states.ACTIVE

    def _power_off(self):
        count = 0
        while not self._is_power_off():
            count += 1
            if count > 3:
                return baremetal_states.ERROR
            try:
                self._snmp.power_off()
                #self._exec_snmpset_tool("i 2")
            except Exception:
                LOG.exception("power_off failed")
            time.sleep(5)
        return baremetal_states.DELETED

    def _reboot(self):
        count = 0
        if self._is_power_off():
            return self._power_on()
        else:
            try:
                self._snmp.reboot()
                #self._exec_snmpset_tool("i 3")
            except Exception:
                LOG.exception("reboot failed")
            time.sleep(5)
        return baremetal_states.ACTIVE

    def _power_status(self):
        #out_err = self._exec_snmpget_tool("")
        out_err = self._snmp.power_status()
        LOG.debug("in power status %s", out_err)
        return out_err[0]

    def _is_power_off(self):
        r = self._power_status()
        LOG.debug("is power_off %s", r.endswith("2\n"))
        return r.endswith("2\n")

    def is_power_on(self):
        r = self._power_status()
        LOG.debug("is power_on %s", r.endswith("1\n"))
        return r.endswith("1\n")

    def start_console(self, port, node_id):
        raise SnmpNetBootError(-1, "Not Implemented")

    def stop_console(self, node_id):
	pass
        #raise SnmpNetBootError(-1, "Not Implemented")
