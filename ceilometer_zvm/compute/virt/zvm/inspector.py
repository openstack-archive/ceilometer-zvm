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


import six

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.i18n import _
from ceilometer_zvm.compute.virt.zvm import exception
from ceilometer_zvm.compute.virt.zvm import utils as zvmutils
from oslo_config import cfg
from oslo_utils import units


zvm_opts = [
    cfg.URIOpt('zvm_cloud_connector_url',
               help="""
URL to be used to communicate with z/VM Cloud Connector.
Example: https://10.10.10.1:8080.
"""),
            ]


class ZVMInspector(virt_inspector.Inspector):

    def __init__(self, conf):
        super(ZVMInspector, self).__init__(conf)
        self.conf.register_opts(zvm_opts)
        self._reqh = zvmutils.zVMConnectorRequestHandler(
            self.conf.zvm_cloud_connector_url)

    def inspect_vnics(self, instance, duration):
        nics_data = self._inspect_inst_data(instance, 'vnics')
        # Construct the final result
        for nic in nics_data:
            yield virt_inspector.InterfaceStats(name=nic['nic_vdev'],
                                                mac=None,
                                                fref=None,
                                                parameters=None,
                                                rx_bytes=nic['nic_rx'],
                                                rx_packets=nic['nic_fr_rx'],
                                                rx_errors=None,
                                                rx_drop=None,
                                                tx_bytes=nic['nic_tx'],
                                                tx_packets=nic['nic_fr_tx'],
                                                tx_errors=None,
                                                tx_drop=None
                                                )

    def inspect_instance(self, instance, duration):
        inst_stats = self._inspect_inst_data(instance, 'stats')
        cpu_number = inst_stats['guest_cpus']
        used_cpu_time = (inst_stats['used_cpu_time_us'] * units.k)
        used_mem_mb = inst_stats['used_mem_kb'] / units.Ki
        # Construct the final result
        return virt_inspector.InstanceStats(cpu_number=cpu_number,
                                            cpu_time=used_cpu_time,
                                            memory_usage=used_mem_mb
                                            )

    def _inspect_inst_data(self, instance, inspect_type):
        inspect_data = {}
        inst_name = zvmutils.get_inst_name(instance)
        msg_shutdown = _("Can not get vm info in shutdown state "
                    "for %s") % inst_name
        msg_notexist = _("Can not get vm info for %s, vm not exist"
                         ) % inst_name
        msg_nodata = _("Failed to get vm info for %s") % inst_name
        # zvm inspector can not get instance info in shutdown stat
        if zvmutils.get_inst_power_state(instance) == 0x04:
            raise virt_inspector.InstanceShutOffException(msg_shutdown)
        try:
            if inspect_type == 'stats':
                inspect_data = self._reqh.call('guest_inspect_stats',
                                                 inst_name)
            elif inspect_type == 'vnics':
                inspect_data = self._reqh.call('guest_inspect_vnics',
                                                 inst_name)
        except Exception as err:
            msg_nodata += _(". Error: %s") % six.text_type(err)
            raise virt_inspector.NoDataException(msg_nodata)

        # Check the inst data is in the returned result
        index_key = inst_name.upper()
        if index_key not in inspect_data:
            # Check the reason: shutdown or not exist or other error
            power_stat = ''
            try:
                power_stat = self._reqh.call('guest_get_power_state',
                                               inst_name)
            except exception.ZVMConnectorRequestFailed as err:
                if err.results['overallRC'] == 404:
                    # instance not exists
                    raise virt_inspector.InstanceNotFoundException(msg_notexist
                                                                   )
                else:
                    msg_nodata += _(". Error: %s") % six.text_type(err)
                    raise virt_inspector.NoDataException(msg_nodata)
            except Exception as err:
                msg_nodata += _(". Error: %s") % six.text_type(err)
                raise virt_inspector.NoDataException(msg_nodata)

            if power_stat == 'off':
                raise virt_inspector.InstanceShutOffException(msg_shutdown)
            else:
                raise virt_inspector.NoDataException(msg_nodata)
        else:
            return inspect_data[index_key]
