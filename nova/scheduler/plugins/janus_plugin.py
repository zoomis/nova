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

from janusclient import client as jclient

janus_plugin_opts = [
    cfg.StrOpt('janus_host',
               default='http://10.10.20.10',
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
    def __init__(self):
        janus = 'http://%s:%s'%(FLAGS.janus_host,FLAGS.janus_port)
        self._client = jclient.Client(janus)


    def host_select(self, hosts, metric):
        """select host by Janus plugin"""
        LOG.debug(_("call select hosts by Janus plugin (%s) by metric (%s)")%(hosts,metric))
        LOG.debug(_("pass hosts to Janus"))
        # call scheduler backend in Janus
        selectedHosts = hosts
        data = {'metric': metric, 'hosts': hosts}
        try:
            selectedHosts = self._client.novasch.select_hosts(metric, hosts)
            # return hosts from Janus
            LOG.debug(_("receive results from Janus: %s"), selectedHosts)
        except:
            # handling exceptions
            LOG.debug(_("Exception: %s"), selectedHosts)
        return selectedHosts
