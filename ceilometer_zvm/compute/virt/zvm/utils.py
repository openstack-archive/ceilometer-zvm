# Copyright 2015 IBM Corp.
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


import six.moves.urllib.parse as urlparse

from ceilometer_zvm.compute.virt.zvm import conf
from ceilometer_zvm.compute.virt.zvm import exception
from oslo_log import log as logging
from zvmconnector import connector

CONF = conf.CONF
LOG = logging.getLogger(__name__)


def get_inst_name(instance):
    return getattr(instance, 'OS-EXT-SRV-ATTR:instance_name', None)


def get_inst_power_state(instance):
    return getattr(instance, 'OS-EXT-STS:power_state', None)


class zVMConnectorRequestHandler(object):

    def __init__(self):
        _url = urlparse.urlparse(CONF.zvm_cloud_connector_url)
        self._conn = connector.ZVMConnector(_url.hostname, _url.port)

    def call(self, func_name, *args, **kwargs):
        results = self._conn.send_request(func_name, *args, **kwargs)
        if results['overallRC'] == 0:
            return results['output']
        else:
            msg = ("z/VM Cloud Connector request %(api)s failed with "
                   "parameters: %(args)s %(kwargs)s .  Results: %(results)s" %
                   {'api': func_name, 'args': str(args), 'kwargs': str(kwargs),
                    'results': str(results)})
            LOG.debug(msg)
            raise exception.ZVMConnectorRequestFailed(msg=msg, results=results)
