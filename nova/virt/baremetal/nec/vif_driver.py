from nova import flags
from nova.openstack.common import log as logging
from nova import exception

from nova.virt.baremetal import vif_driver
from nova.virt.baremetal.nec.vifinfo_client import VIFINFOClient

from webob import exc

FLAGS = flags.FLAGS

LOG = logging.getLogger(__name__)


class NECVIFDriver(vif_driver.BareMetalVIFDriver):

    def _after_plug(self, instance, network, mapping, pif):
        client = VIFINFOClient(FLAGS.quantum_connection_host, FLAGS.quantum_connection_port)
        client.create_vifinfo(mapping['vif_uuid'], pif.datapath_id, pif.port_no)

    def _after_unplug(self, instance, network, mapping, pif):
        client = VIFINFOClient(FLAGS.quantum_connection_host, FLAGS.quantum_connection_port)
        try:
            client.delete_vifinfo(mapping['vif_uuid'])
        except (exception.NovaException, exc.HTTPNotFound, exc.HTTPInternalServerError), e:
            LOG.warn("client.delete_vifinfo(%s) is failed. (unplugging is continued): %s", mapping['vif_uuid'], e)
