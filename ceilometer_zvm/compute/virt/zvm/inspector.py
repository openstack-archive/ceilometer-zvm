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
from oslo_utils import timeutils
from oslo_utils import units

from ceilometer_zvm.compute.virt.zvm import utils as zvmutils


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
    cfg.StrOpt('xcat_zhcp_nodename',
               default='zhcp',
               help='xCat zHCP nodename in xCAT '),
    cfg.StrOpt('zvm_host',
               default=None,
               help='z/VM host that managed by xCAT MN.'),
    cfg.StrOpt('zvm_xcat_master',
               default='xcat',
               help='The xCAT MM node name'),
    cfg.IntOpt('cache_update_interval',
               default=600,
               help="Cached data update interval"),
]


CONF = cfg.CONF
CONF.register_opts(zvm_ops, group='zvm')

LOG = log.getLogger(__name__)


class ZVMInspector(virt_inspector.Inspector):

    def __init__(self):
        self.cache = zvmutils.CacheData()
        self.cache_expiration = timeutils.utcnow_ts()

        self.instances = {}
        self.zhcp_info = {
            'nodename': CONF.zvm.xcat_zhcp_nodename,
            'hostname': zvmutils.get_node_hostname(
                            CONF.zvm.xcat_zhcp_nodename),
            'userid': zvmutils.get_userid(CONF.zvm.xcat_zhcp_nodename)
        }

    def _update_inst_cpu_mem_stat(self, instances):
        inst_pis = zvmutils.image_performance_query(
                                self.zhcp_info['nodename'], instances.values())

        for inst_name, userid in instances.items():
            if userid not in inst_pis.keys():
                # Not performance data returned for this virtual machine
                continue

            with zvmutils.expect_invalid_xcat_resp_data():
                guest_cpus = int(inst_pis[userid]['guest_cpus'])
                used_cpu_time = inst_pis[userid]['used_cpu_time']
                used_cpu_time = int(used_cpu_time.partition(' ')[0]) * units.k
                used_memory = inst_pis[userid]['used_memory']
                used_memory = int(used_memory.partition(' ')[0]) / units.Ki

            inst_stat = {'nodename': inst_name,
                         'userid': userid,
                         'guest_cpus': guest_cpus,
                         'used_cpu_time': used_cpu_time,
                         'used_memory': used_memory}

            self.cache.set(inst_stat)

    def _update_inst_nic_stat(self, instances):
        vsw_dict = zvmutils.virutal_network_vswitch_query_iuo_stats(
                                                    self.zhcp_info['nodename'])
        with zvmutils.expect_invalid_xcat_resp_data():
            for vsw in vsw_dict['vswitches']:
                for nic in vsw['nics']:
                    for inst_name, userid in instances.items():
                        if nic['userid'].upper() == userid.upper():
                            nic_entry = {'vswitch_name': vsw['vswitch_name'],
                                         'nic_vdev': nic['vdev'],
                                         'nic_fr_rx': int(nic['nic_fr_rx']),
                                         'nic_fr_tx': int(nic['nic_fr_tx']),
                                         'nic_rx': int(nic['nic_rx']),
                                         'nic_tx': int(nic['nic_tx'])}
                            inst_stat = self.cache.get(inst_name)
                            if inst_stat is None:
                                inst_stat = {
                                    'nodename': inst_name,
                                    'userid': userid,
                                    'nics': [nic_entry]
                                }
                            else:
                                inst_stat['nics'].append(nic_entry)
                            self.cache.set(inst_stat)

    def _update_cache(self, meter, instances={}):
        if instances == {}:
            self.cache.clear()
            self.cache_expiration = (timeutils.utcnow_ts() +
                                     CONF.zvm.cache_update_interval)
            instances = self.instances = zvmutils.list_instances(
                                                                self.zhcp_info)

        if meter in ('cpus', 'memory.usage'):
            self._update_inst_cpu_mem_stat(instances)

    def _check_expiration_and_update_cache(self, meter):
        now = timeutils.utcnow_ts()
        if now >= self.cache_expiration:
            self._update_cache(meter)

    def _get_inst_stat(self, meter, instance):
        self._check_expiration_and_update_cache(meter)

        inst_name = zvmutils.get_inst_name(instance)
        inst_stat = self.cache.get(inst_name)

        if inst_stat is None:
            userid = (self.instances.get(inst_name) or
                        zvmutils.get_userid(inst_name))
            self._update_cache(meter, {inst_name: userid})
            inst_stat = self.cache.get(inst_name)

        if inst_stat is None:
            raise virt_inspector.InstanceNotFoundException()
        else:
            return inst_stat

    def inspect_cpus(self, instance):
        inst_stat = self._get_inst_stat('cpus', instance)
        return virt_inspector.CPUStats(number=inst_stat['guest_cpus'],
                                       time=inst_stat['used_cpu_time'])

    def inspect_memory_usage(self, instance, duration=None):
        inst_stat = self._get_inst_stat('memory.usage', instance)
        return virt_inspector.MemoryUsageStats(usage=inst_stat['used_memory'])

    def inspect_vnics(self, instance):
        pass
