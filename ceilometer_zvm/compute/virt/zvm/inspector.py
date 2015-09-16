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


CONF = cfg.CONF
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
