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
