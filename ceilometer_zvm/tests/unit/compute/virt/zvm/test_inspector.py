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


import mock
import unittest

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer_zvm.compute.virt.zvm import exception as zvmexception
from ceilometer_zvm.compute.virt.zvm import inspector as zvminspector
from ceilometer_zvm.compute.virt.zvm import utils as zvmutils


class TestZVMInspector(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        conf = mock.Mock()
        conf.zvm_cloud_connector_url = 'https://1.1.1.1:1111'
        self._inspector = zvminspector.ZVMInspector(conf)
        self._inst = mock.MagicMock()
        self._stats_dict = {'guest_cpus': 1,
                            'used_cpu_time_us': 7185838,
                            'elapsed_cpu_time_us': 35232895,
                            'min_cpu_count': 2,
                            'max_cpu_limit': 10000,
                            'samples_cpu_in_use': 0,
                            'samples_cpu_delay': 0,
                            'used_mem_kb': 390232,
                            'max_mem_kb': 3097152,
                            'min_mem_kb': 0,
                            'shared_mem_kb': 5222192
                            }
        self._vnics_list = [{'vswitch_name': 'vsw1',
                            'nic_vdev': '0600',
                            'nic_fr_rx': 99999,
                            'nic_fr_tx': 99999,
                            'nic_rx': 9999999,
                            'nic_tx': 9999999,
                            'nic_fr_rx_dsc': 0,
                            'nic_fr_tx_dsc': 0,
                            'nic_fr_rx_err': 0,
                            'nic_fr_tx_err': 0},
                            {'vswitch_name': 'vsw2',
                            'nic_vdev': '0700',
                            'nic_fr_rx': 88888,
                            'nic_fr_tx': 88888,
                            'nic_rx': 8888888,
                            'nic_tx': 8888888,
                            'nic_fr_rx_dsc': 0,
                            'nic_fr_tx_dsc': 0,
                            'nic_fr_rx_err': 0,
                            'nic_fr_tx_err': 0}]

    @mock.patch.object(zvminspector.ZVMInspector, "_inspect_inst_data")
    def test_inspect_instance(self, inspect_inst):
        inspect_inst.return_value = self._stats_dict
        rdata = self._inspector.inspect_instance(self._inst, 0)
        inspect_inst.assert_called_once_with(self._inst, 'stats')
        self.assertIsInstance(rdata, virt_inspector.InstanceStats)
        self.assertEqual(rdata.cpu_number, 1)
        self.assertEqual(rdata.cpu_time, 7185838000)
        self.assertEqual(rdata.memory_usage, 381)

    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_inspect_inst_data")
    @mock.patch.object(zvmutils, 'get_inst_name')
    def test_inspect_vnics(self, get_inst_name, inspect_data):
        get_inst_name.return_value = 'INST1'
        inspect_data.return_value = self._vnics_list
        interface = list(self._inspector.inspect_vnics(
            {'inst1': 'INST1'}, 0))[0]
        if interface.name == '0600':
            self.assertEqual(99999, interface.rx_packets)
        else:
            self.assertEqual(8888888, interface.rx_bytes)
        inspect_data.assert_called_once_with({'inst1': 'INST1'}, 'vnics')

    @mock.patch.object(zvmutils.zVMConnectorRequestHandler, 'call')
    @mock.patch.object(zvmutils, 'get_inst_power_state')
    @mock.patch.object(zvmutils, 'get_inst_name')
    def test_private_inspect_inst_type_stats(self, inst_name, inst_power_state,
                                             sdkclient_call):
        inst_name.return_value = 'FAKEINST'
        inst_power_state.return_value = 0x01
        sdkclient_call.return_value = {'FAKEINST': self._stats_dict}
        rdata = self._inspector._inspect_inst_data(self._inst, 'stats')
        inst_name.assert_called_once_with(self._inst)
        inst_power_state.assert_called_once_with(self._inst)
        sdkclient_call.assert_called_once_with('guest_inspect_stats',
                                               'FAKEINST')
        self.assertDictEqual(rdata, self._stats_dict)

    @mock.patch.object(zvmutils.zVMConnectorRequestHandler, 'call')
    @mock.patch.object(zvmutils, 'get_inst_power_state')
    @mock.patch.object(zvmutils, 'get_inst_name')
    def test_private_inspect_inst_type_vnics(self, inst_name, inst_power_state,
                                             sdkclient_call):
        inst_name.return_value = 'FAKEINST'
        inst_power_state.return_value = 0x01
        sdkclient_call.return_value = {'FAKEINST': self._vnics_list}
        rdata = self._inspector._inspect_inst_data(self._inst, 'vnics')
        inst_name.assert_called_once_with(self._inst)
        inst_power_state.assert_called_once_with(self._inst)
        sdkclient_call.assert_called_once_with('guest_inspect_vnics',
                                               'FAKEINST')
        self.assertListEqual(rdata, self._vnics_list)

    @mock.patch.object(zvmutils.zVMConnectorRequestHandler, 'call')
    @mock.patch.object(zvmutils, 'get_inst_power_state')
    @mock.patch.object(zvmutils, 'get_inst_name')
    def test_private_inspect_inst_power_off(self, inst_name,
                                              inst_power_state,
                                              sdkclient_call):
        inst_name.return_value = 'FAKEINST'
        inst_power_state.return_value = 0x04
        self.assertRaises(virt_inspector.InstanceShutOffException,
                          self._inspector._inspect_inst_data,
                          self._inst, 'stats')
        inst_name.assert_called_once_with(self._inst)
        inst_power_state.assert_called_once_with(self._inst)
        sdkclient_call.assert_not_called()

    @mock.patch.object(zvmutils.zVMConnectorRequestHandler, 'call')
    @mock.patch.object(zvmutils, 'get_inst_power_state')
    @mock.patch.object(zvmutils, 'get_inst_name')
    def test_private_inspect_inst_not_exist(self, inst_name,
                                              inst_power_state,
                                              sdkclient_call):
        inst_name.return_value = 'FAKEINST'
        inst_power_state.return_value = 0x01
        sdkclient_call.side_effect = [{},
                                      zvmexception.ZVMConnectorRequestFailed(
                                          msg='SDK Request Failed',
                                          results={'overallRC': 404,
                                                   'output': ''})
                                      ]
        self.assertRaises(virt_inspector.InstanceNotFoundException,
                          self._inspector._inspect_inst_data,
                          self._inst, 'stats')
        inst_name.assert_called_once_with(self._inst)
        inst_power_state.assert_called_once_with(self._inst)

    @mock.patch.object(zvmutils.zVMConnectorRequestHandler, 'call')
    @mock.patch.object(zvmutils, 'get_inst_power_state')
    @mock.patch.object(zvmutils, 'get_inst_name')
    def test_private_inspect_inst_other_exception(self, inst_name,
                                                    inst_power_state,
                                                    sdkclient_call):
        inst_name.return_value = 'FAKEINST'
        inst_power_state.return_value = 0x01
        sdkclient_call.side_effect = Exception()
        self.assertRaises(virt_inspector.NoDataException,
                          self._inspector._inspect_inst_data,
                          self._inst, 'stats')
        inst_name.assert_called_once_with(self._inst)
        inst_power_state.assert_called_once_with(self._inst)
        sdkclient_call.assert_called_with('guest_inspect_stats', 'FAKEINST')

    @mock.patch.object(zvmutils.zVMConnectorRequestHandler, 'call')
    @mock.patch.object(zvmutils, 'get_inst_power_state')
    @mock.patch.object(zvmutils, 'get_inst_name')
    def test_private_inspect_inst_null_data_shutdown(self, inst_name,
                                                       inst_power_state,
                                                       sdkclient_call):
        inst_name.return_value = 'FAKEINST'
        inst_power_state.return_value = 0x01
        sdkclient_call.side_effect = [{}, 'off']
        self.assertRaises(virt_inspector.InstanceShutOffException,
                          self._inspector._inspect_inst_data,
                          self._inst, 'stats')
        inst_name.assert_called_once_with(self._inst)
        inst_power_state.assert_called_once_with(self._inst)

    @mock.patch.object(zvmutils.zVMConnectorRequestHandler, 'call')
    @mock.patch.object(zvmutils, 'get_inst_power_state')
    @mock.patch.object(zvmutils, 'get_inst_name')
    def test_private_inspect_inst_null_data_active(self, inst_name,
                                                     inst_power_state,
                                                     sdkclient_call):
        inst_name.return_value = 'FAKEINST'
        inst_power_state.return_value = 0x01
        sdkclient_call.side_effect = [{}, 'on']
        self.assertRaises(virt_inspector.NoDataException,
                          self._inspector._inspect_inst_data,
                          self._inst, 'stats')
        inst_name.assert_called_once_with(self._inst)
        inst_power_state.assert_called_once_with(self._inst)

    @mock.patch.object(zvmutils.zVMConnectorRequestHandler, 'call')
    @mock.patch.object(zvmutils, 'get_inst_power_state')
    @mock.patch.object(zvmutils, 'get_inst_name')
    def test_private_inspect_inst_null_data_unknown_exception(self,
            inst_name, inst_power_state, sdkclient_call):
        inst_name.return_value = 'FAKEINST'
        inst_power_state.return_value = 0x01
        sdkclient_call.side_effect = [{}, Exception()]
        self.assertRaises(virt_inspector.NoDataException,
                          self._inspector._inspect_inst_data,
                          self._inst, 'stats')
        inst_name.assert_called_once_with(self._inst)
        inst_power_state.assert_called_once_with(self._inst)
