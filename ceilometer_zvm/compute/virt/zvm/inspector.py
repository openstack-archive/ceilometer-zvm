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


from ceilometer.compute.virt import inspector as virt_inspector
from oslo_config import cfg
from oslo_log import log


zvm_ops = [
    cfg.StrOpt('zvm_xcat_server',
               default=None,
               help='Host name or IP address of xCAT management_node'),
    cfg.StrOpt('zvm_xcat_username',
               default=None,
               help='xCAT username'),
    cfg.StrOpt('zvm_xcat_password',
               default=None,
               secret=True,
               help='Password of the xCAT user'),
    cfg.IntOpt('zvm_xcat_connection_timeout',
               default=600,
               help="The number of seconds wait for xCAT MN response"),
]


CONF = cfg.CONF
CONF.register_opts(zvm_ops, group='zvm')

LOG = log.getLogger(__name__)


class ZVMInspector(virt_inspector.Inspector):

    def __init__(self):
        pass

    def inspect_cpus(self, instance):
        pass

    def inspect_memory_usage(self, instance, duration=None):
        pass

    def inspect_vnics(self, instance):
        pass
