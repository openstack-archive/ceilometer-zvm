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
from oslo_serialization import jsonutils
from oslotest import base

from ceilometer_zvm.compute.virt.zvm import inspector
from ceilometer_zvm.compute.virt.zvm import utils as zvmutils


class TestXCATUrl(base.BaseTestCase):

    def setUp(self):
        self.CONF = self.useFixture(fixture_config.Config(inspector.CONF)).conf
        self.CONF.set_override('zvm_xcat_username', 'user', 'zvm')
        self.CONF.set_override('zvm_xcat_password', 'pwd', 'zvm')
        super(TestXCATUrl, self).setUp()
        self.xcaturl = zvmutils.XCATUrl()

    def test_xdsh(self):
        url = ("/xcatws/nodes/fakenode/dsh"
               "?userName=user&password=pwd&format=json")
        self.assertEqual(self.xcaturl.xdsh("/fakenode"), url)

    def test_gettab(self):
        url = ("/xcatws/tables/table"
               "?userName=user&password=pwd&format=json&addp")
        self.assertEqual(self.xcaturl.gettab('/table', '&addp'), url)

    def test_lsdef_node(self):
        url = ("/xcatws/nodes/fakenode"
               "?userName=user&password=pwd&format=json")
        self.assertEqual(self.xcaturl.lsdef_node("/fakenode"), url)

    def test_tabdump(self):
        url = ("/xcatws/tables/table"
               "?userName=user&password=pwd&format=json&addp")
        self.assertEqual(self.xcaturl.tabdump('/table', '&addp'), url)


class TestXCATConnection(base.BaseTestCase):

    def setUp(self):
        self.CONF = self.useFixture(fixture_config.Config(inspector.CONF)).conf
        self.CONF.set_override('zvm_xcat_server', '1.1.1.1', 'zvm')
        self.CONF.set_override('zvm_xcat_username', 'user', 'zvm')
        self.CONF.set_override('zvm_xcat_password', 'pwd', 'zvm')
        super(TestXCATConnection, self).setUp()
        self.conn = zvmutils.XCATConnection()

    def test_request(self):
        with mock.patch.object(self.conn, 'conn') as fake_conn:
            fake_res = mock.Mock()
            fake_res.status = 200
            fake_res.reason = 'OK'
            fake_res.read.return_value = 'data'
            fake_conn.getresponse.return_value = fake_res

            exp_data = {'status': 200,
                        'reason': 'OK',
                        'message': 'data'}
            res_data = self.conn.request("GET", 'url')
            self.assertEqual(exp_data, res_data)

    def test_request_failed(self):
        with mock.patch.object(self.conn, 'conn') as fake_conn:
            fake_res = mock.Mock()
            fake_res.status = 500
            fake_res.reason = 'INVALID'
            fake_res.read.return_value = 'err data'
            fake_conn.getresponse.return_value = fake_res

            self.assertRaises(zvmutils.ZVMException,
                              self.conn.request, 'GET', 'url')


class TestZVMUtils(base.BaseTestCase):

    def setUp(self):
        self.CONF = self.useFixture(fixture_config.Config(inspector.CONF)).conf
        self.CONF.set_override('zvm_xcat_server', '1.1.1.1', 'zvm')
        self.CONF.set_override('zvm_xcat_username', 'user', 'zvm')
        self.CONF.set_override('zvm_xcat_password', 'pwd', 'zvm')
        super(TestZVMUtils, self).setUp()

    @mock.patch('ceilometer_zvm.compute.virt.zvm.utils.XCATConnection.request')
    def test_xcat_request(self, xcat_req):
        xcat_req.return_value = {'message': jsonutils.dumps(
                                    {'data': [{'data': ['data']}]})}
        self.assertEqual([['data']],
                         zvmutils.xcat_request("GET", 'url')['data'])

    @mock.patch('ceilometer_zvm.compute.virt.zvm.utils.xcat_request')
    def test_get_userid(self, xcat_req):
        xcat_req.return_value = {'info': [['userid=fakeuser']]}
        self.assertEqual('fakeuser', zvmutils.get_userid('fakenode'))

    @mock.patch('ceilometer_zvm.compute.virt.zvm.utils.xcat_request')
    def test_xdsh(self, xcat_req):
        zvmutils.xdsh('node', 'cmds')
        xcat_req.assert_any_call('PUT',
            '/xcatws/nodes/node/dsh?userName=user&password=pwd&format=json',
            ['command=cmds'])


class TestCacheData(base.BaseTestCase):

    def setUp(self):
        super(TestCacheData, self).setUp()
        self.cache_data = zvmutils.CacheData()

    def tearDown(self):
        self.cache_data.clear()
        super(TestCacheData, self).tearDown()

    def test_set(self):
        self.cache_data.set({'nodename': 'node'})
        self.assertEqual({'nodename': 'node'}, self.cache_data.cache['node'])

    def test_get(self):
        self.cache_data.set({'nodename': 'node'})
        self.assertEqual({'nodename': 'node'}, self.cache_data.get('node'))

    def test_delete(self):
        self.cache_data.set({'nodename': 'node'})
        self.cache_data.delete('node')
        self.assertEqual(None, self.cache_data.get('node'))

    def test_clear(self):
        self.cache_data.set({'nodename': 'node1'})
        self.cache_data.set({'nodename': 'node2'})
        self.cache_data.clear()
        self.assertEqual({}, self.cache_data.cache)
