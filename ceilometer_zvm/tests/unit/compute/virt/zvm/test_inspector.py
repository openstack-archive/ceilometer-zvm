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

from ceilometer.compute.virt import inspector as virt_inspertor
from oslo_config import fixture as fixture_config
from oslo_utils import timeutils
from oslotest import base

from ceilometer_zvm.compute.virt.zvm import inspector as zvm_inspector
from ceilometer_zvm.compute.virt.zvm import utils as zvmutils


class TestZVMInspector(base.BaseTestCase):

    def setUp(self):
        self.CONF = self.useFixture(
                            fixture_config.Config(zvm_inspector.CONF)).conf
        self.CONF.set_override('xcat_zhcp_nodename', 'zhcp', 'zvm')
        super(TestZVMInspector, self).setUp()

        get_nhn = mock.MagicMock(return_value='zhcp.com')
        get_uid = mock.MagicMock(return_value='zhcp')
        with mock.patch.multiple(zvmutils, get_node_hostname=get_nhn,
                                 get_userid=get_uid):
            self.inspector = zvm_inspector.ZVMInspector()

    def test_init(self):
        self.assertEqual('zhcp', self.inspector.zhcp_info['nodename'])
        self.assertEqual('zhcp.com', self.inspector.zhcp_info['hostname'])
        self.assertEqual('zhcp', self.inspector.zhcp_info['userid'])

    @mock.patch.object(zvmutils, 'image_performance_query')
    def test_update_inst_cpu_mem_stat(self, ipq):
        ipq.return_value = {'INST1': {'userid': 'INST1',
                                      'guest_cpus': '2',
                                      'used_cpu_time': '1710205201 uS',
                                      'used_memory': '4189268 KB'},
                            'INST2': {'userid': 'INST2',
                                      'guest_cpus': '4',
                                      'used_cpu_time': '1710205201 uS',
                                      'used_memory': '4189268 KB'}}
        inst_list = {'inst1': 'INST1', 'inst2': 'INST2'}
        self.inspector._update_inst_cpu_mem_stat(inst_list)

        exp1 = {'guest_cpus': 2,
                'nodename': 'inst1',
                'used_cpu_time': 1710205201000,
                'used_memory': 4091,
                'userid': 'INST1'}
        self.assertEqual(exp1, self.inspector.cache.get('inst1'))
        self.assertEqual(4, self.inspector.cache.get('inst2')['guest_cpus'])

    @mock.patch.object(zvmutils, 'image_performance_query')
    def test_update_inst_cpu_mem_stat_invalid_data(self, ipq):
        ipq.return_value = {'INST1': {'userid': 'INST1', 'guest_cpus': 's'}}
        self.assertRaises(zvmutils.ZVMException,
                          self.inspector._update_inst_cpu_mem_stat,
                          {'inst1': 'INST1'})

    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_update_inst_cpu_mem_stat")
    @mock.patch.object(zvmutils, 'list_instances')
    def test_update_cache_all(self, list_inst, upd):
        inst_list = {'inst1': 'INST1', 'inst2': 'INST2'}
        list_inst.return_value = inst_list
        self.inspector._update_cache("cpus", {})
        list_inst.assert_called_with(self.inspector.zhcp_info)
        upd.assert_called_with(inst_list)

    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_update_inst_cpu_mem_stat")
    def test_update_cache_one_inst(self, upd):
        inst = {'inst1': 'INST1'}
        self.inspector._update_cache('memory.usage', inst)
        upd.assert_called_with(inst)

    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_update_cache")
    def test_check_expiration_and_update_cache(self, udc):
        self.inspector._check_expiration_and_update_cache('cpus')
        udc.assert_called_once_with('cpus')

    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_update_cache")
    def test_check_expiration_and_update_cache_no_update(self, udc):
        self.inspector.cache_expiration = timeutils.utcnow_ts() + 100
        self.inspector._check_expiration_and_update_cache('cpus')
        udc.assert_not_called()

    @mock.patch.object(zvmutils, 'get_inst_name')
    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_check_expiration_and_update_cache")
    def test_get_inst_stat(self, check_update, get_name):
        get_name.return_value = 'inst1'
        self.inspector.cache.set({'guest_cpus': 2, 'nodename': 'inst1'})

        inst_stat = self.inspector._get_inst_stat('cpus', {'inst1': 'INST1'})
        self.assertEqual(2, inst_stat['guest_cpus'])
        check_update.assert_called_once_with('cpus')

    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_update_cache")
    @mock.patch.object(zvmutils, 'get_userid')
    @mock.patch.object(zvmutils, 'get_inst_name')
    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_check_expiration_and_update_cache")
    def test_get_inst_stat_not_found(self, check_update, get_name,
                                     get_uid, update):
        get_name.return_value = 'inst1'
        get_uid.return_value = 'INST1'

        self.assertRaises(virt_inspertor.InstanceNotFoundException,
                          self.inspector._get_inst_stat, 'cpus',
                          {'inst1': 'INST1'})
        check_update.assert_called_once_with('cpus')
        update.assert_called_once_with('cpus', {'inst1': 'INST1'})

    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_update_cache")
    @mock.patch.object(zvmutils, 'get_userid')
    @mock.patch("ceilometer_zvm.compute.virt.zvm.utils.CacheData.get")
    @mock.patch.object(zvmutils, 'get_inst_name')
    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_check_expiration_and_update_cache")
    def test_get_inst_stat_update_cache(self, check_update, get_name,
                                        cache_get, get_uid, update):
        get_name.return_value = 'inst1'
        cache_get.side_effect = [None, {'guest_cpus': 2, 'nodename': 'inst1'}]
        get_uid.return_value = 'INST1'

        inst_stat = self.inspector._get_inst_stat('cpus', {'inst1': 'INST1'})
        self.assertEqual(2, inst_stat['guest_cpus'])
        check_update.assert_called_once_with('cpus')
        update.assert_called_once_with('cpus', {'inst1': 'INST1'})

    @mock.patch("ceilometer_zvm.compute.virt.zvm.inspector.ZVMInspector."
                "_get_inst_stat")
    def test_inspect_cpus(self, get_stat):
        get_stat.return_value = {'guest_cpus': 2, 'used_cpu_time': 99999999}
        cpu_stat = self.inspector.inspect_cpus(None)
        self.assertEqual(2, cpu_stat.number)
        self.assertEqual(99999999, cpu_stat.time)
        get_stat.assert_called_once_with('cpus', None)
