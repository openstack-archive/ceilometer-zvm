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

from oslo_config import fixture as fixture_config
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
