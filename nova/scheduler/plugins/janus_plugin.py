#
#    Copyright (C) 2012.
#    Eliot J. Kang <joonmyung.kang@utoronto.ca>
#    Hadi Bannazadeh <hadi.bannazadeh@utoronto.ca>
#    Alberto Leon-Garcia <alberto.leongarcia@utoronto.ca>
#

"""
scheduling by Janus
"""
from nova import flags
from nova.openstack.common import cfg
from nova.scheduler import plugins
from nova.openstack.common import log as logging

import httplib2
import json
import requests

janus_plugin_opts = [
    cfg.StrOpt('janus_host',
               default='http://localhost',
               help='SDI manager host name'),
    cfg.StrOpt('janus_port',
               default='9091',
               help='SDI manager host port'),
    ]

FLAGS = flags.FLAGS
FLAGS.register_opts(janus_plugin_opts)

LOG = logging.getLogger(__name__)

class JanusPlugin(plugins.BaseHostPlugin):
    """Disk Filter with over subscription flag"""

    def host_select(self, hosts, metric):
        """select host by Janus plugin"""
        LOG.debug(_("call select hosts by Janus plugin (%s) by metric (%s)")%(hosts,metric))
        LOG.debug(_("pass hosts to Janus"))
        # call scheduler backend in Janus
        janus = 'http://%s:%s/filterhosts'%(FLAGS.janus_host,FLAGS.janus_port)
        headers = {'content-type': 'application/json'}
        selectedHosts = hosts
        data = {'metric': metric, 'hosts': hosts}
        try:
            r = requests.put(janus, data=json.dumps(data), headers=headers)
            selectedHosts = r.json
            # return hosts from Janus
            LOG.debug(_("receive results from Janus: %s"), selectedHosts)
        except:
            # handling exceptions
            LOG.debug(_("Exception: %s"), selectedHosts)
        return selectedHosts
