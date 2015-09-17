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

from ceilometer_zvm.compute.virt.zvm import inspector as zvm_inspector
from ceilometer_zvm.compute.virt.zvm import utils as zvmutils


class TestXCATUrl(base.BaseTestCase):

    def setUp(self):
        self.CONF = self.useFixture(
                            fixture_config.Config(zvm_inspector.CONF)).conf
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
        self.CONF = self.useFixture(
                            fixture_config.Config(zvm_inspector.CONF)).conf
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
        self.CONF = self.useFixture(
                            fixture_config.Config(zvm_inspector.CONF)).conf
        self.CONF.set_override('zvm_xcat_server', '1.1.1.1', 'zvm')
        self.CONF.set_override('zvm_xcat_username', 'user', 'zvm')
        self.CONF.set_override('zvm_xcat_password', 'pwd', 'zvm')
        self.CONF.set_override('zvm_host', 'zvmhost1', 'zvm')
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

    @mock.patch('ceilometer_zvm.compute.virt.zvm.utils.xcat_request')
    def test_get_node_hostname(self, xcat_req):
        xcat_req.return_value = {'data': [['hostname']]}
        self.assertEqual('hostname', zvmutils.get_node_hostname('nodename'))

    @mock.patch.object(zvmutils, 'xcat_request')
    def test_list_instances(self, xcat_req):
        resp_list = [
            'toss',
            '"xcat","zhcp.com","xcat"',
            '"zhcp","zhcp.com","zhcp"',
            '"zvmhost1","zhcp.com",""',
            '"node1","zhcp.com","node1"',
            '"node2","zhcp.com","node2"',
            '"node3","zhcp2.com","node3"',
        ]
        xcat_req.return_value = {'data': [resp_list]}

        exp_list = {'node1': 'NODE1', 'node2': 'NODE2'}
        hcp_info = {'nodename': 'zhcp',
                    'hostname': 'zhcp.com',
                    'userid': 'zhcp'}
        self.assertEqual(exp_list, zvmutils.list_instances(hcp_info))

    @mock.patch.object(zvmutils, 'xcat_request')
    def test_list_instances_invalid_data(self, xcat_req):
        resp_list = [
            'toss',
            '"xcat","zhcp.com","xcat"',
            '"zhcp","zhcp.com","zhcp"',
            '"zvmhost1","zhcp.com",""',
            '"node1","zhcp.com"',
        ]
        hcp_info = {'nodename': 'zhcp',
                    'hostname': 'zhcp.com',
                    'userid': 'zhcp'}
        xcat_req.return_value = {'data': [resp_list]}
        self.assertRaises(zvmutils.ZVMException, zvmutils.list_instances,
                          hcp_info)

    @mock.patch.object(zvmutils, 'xdsh')
    def test_image_performance_query(self, dsh):
        res_data = ["zhcp: Number of virtual server IDs: 2 \n"
                    "zhcp: Guest name: INST1\n"
                    "zhcp: Used CPU time: \"1710205201 uS\"\n"
                    "zhcp: Elapsed time: \"6659572798 uS\"\n"
                    "zhcp: Used memory: \"4189268 KB\"\n"
                    "zhcp: Guest CPUs: \"2\"\n"
                    "zhcp: \n"
                    "zhcp: Guest name: INST2\n"
                    "zhcp: Used CPU time: \"1710205201 uS\"\n"
                    "zhcp: Elapsed time: \"6659572798 uS\"\n"
                    "zhcp: Used memory: \"4189268 KB\"\n"
                    "zhcp: Guest CPUs: \"4\"\n"]
        dsh.return_value = {'data': [res_data]}
        inst_list = {'inst1': 'INST1', 'inst2': 'INST2'}

        exp_data = {'INST1': {'userid': 'INST1',
                              'guest_cpus': '2',
                              'used_cpu_time': '1710205201 uS',
                              'used_memory': '4189268 KB'},
                    'INST2': {'userid': 'INST2',
                              'guest_cpus': '4',
                              'used_cpu_time': '1710205201 uS',
                              'used_memory': '4189268 KB'}}
        self.assertEqual(exp_data,
                         zvmutils.image_performance_query('zhcp', inst_list))

    @mock.patch.object(zvmutils, 'xdsh')
    def test_image_performance_query_invalid_xdsh_resp(self, dsh):
        dsh.return_value = {'data': 'invalid data'}
        inst_list = {'inst1': 'INST1', 'inst2': 'INST2'}
        self.assertRaises(zvmutils.ZVMException,
                          zvmutils.image_performance_query, 'zhcp', inst_list)

    @mock.patch.object(zvmutils, 'xdsh')
    def test_virutal_network_vswitch_query_iuo_stats(self, dsh):
        vsw_data = ['zhcp11: vswitch count: 2\n'
                    'zhcp11: \n'
                    'zhcp11: vswitch number: 1\n'
                    'zhcp11: vswitch name: XCATVSW1\n'
                    'zhcp11: uplink count: 1\n'
                    'zhcp11: uplink_conn: 6240\n'
                    'zhcp11: uplink_fr_rx:     3658251\n'
                    'zhcp11: uplink_fr_rx_dsc: 0\n'
                    'zhcp11: uplink_fr_rx_err: 0\n'
                    'zhcp11: uplink_fr_tx:     4209828\n'
                    'zhcp11: uplink_fr_tx_dsc: 0\n'
                    'zhcp11: uplink_fr_tx_err: 0\n'
                    'zhcp11: uplink_rx:        498914052\n'
                    'zhcp11: uplink_tx:        2615220898\n'
                    'zhcp11: bridge_fr_rx:     0\n'
                    'zhcp11: bridge_fr_rx_dsc: 0\n'
                    'zhcp11: bridge_fr_rx_err: 0\n'
                    'zhcp11: bridge_fr_tx:     0\n'
                    'zhcp11: bridge_fr_tx_dsc: 0\n'
                    'zhcp11: bridge_fr_tx_err: 0\n'
                    'zhcp11: bridge_rx:        0\n'
                    'zhcp11: bridge_tx:        0\n'
                    'zhcp11: nic count: 2\n'
                    'zhcp11: nic_id: INST1 0600\n'
                    'zhcp11: nic_fr_rx:        573952\n'
                    'zhcp11: nic_fr_rx_dsc:    0\n'
                    'zhcp11: nic_fr_rx_err:    0\n'
                    'zhcp11: nic_fr_tx:        548780\n'
                    'zhcp11: nic_fr_tx_dsc:    0\n'
                    'zhcp11: nic_fr_tx_err:    4\n'
                    'zhcp11: nic_rx:           103024058\n'
                    'zhcp11: nic_tx:           102030890\n'
                    'zhcp11: nic_id: INST2 0600\n'
                    'zhcp11: nic_fr_rx:        17493\n'
                    'zhcp11: nic_fr_rx_dsc:    0\n'
                    'zhcp11: nic_fr_rx_err:    0\n'
                    'zhcp11: nic_fr_tx:        16886\n'
                    'zhcp11: nic_fr_tx_dsc:    0\n'
                    'zhcp11: nic_fr_tx_err:    4\n'
                    'zhcp11: nic_rx:           3111714\n'
                    'zhcp11: nic_tx:           3172646\n'
                    'zhcp11: vlan count: 0\n'
                    'zhcp11: \n'
                    'zhcp11: vswitch number: 2\n'
                    'zhcp11: vswitch name: XCATVSW2\n'
                    'zhcp11: uplink count: 1\n'
                    'zhcp11: uplink_conn: 6200\n'
                    'zhcp11: uplink_fr_rx:     1608681\n'
                    'zhcp11: uplink_fr_rx_dsc: 0\n'
                    'zhcp11: uplink_fr_rx_err: 0\n'
                    'zhcp11: uplink_fr_tx:     2120075\n'
                    'zhcp11: uplink_fr_tx_dsc: 0\n'
                    'zhcp11: uplink_fr_tx_err: 0\n'
                    'zhcp11: uplink_rx:        314326223',
                    'zhcp11: uplink_tx:        1503721533\n'
                    'zhcp11: bridge_fr_rx:     0\n'
                    'zhcp11: bridge_fr_rx_dsc: 0\n'
                    'zhcp11: bridge_fr_rx_err: 0\n'
                    'zhcp11: bridge_fr_tx:     0\n'
                    'zhcp11: bridge_fr_tx_dsc: 0\n'
                    'zhcp11: bridge_fr_tx_err: 0\n'
                    'zhcp11: bridge_rx:        0\n'
                    'zhcp11: bridge_tx:        0\n'
                    'zhcp11: nic count: 2\n'
                    'zhcp11: nic_id: INST1 1000\n'
                    'zhcp11: nic_fr_rx:        34958\n'
                    'zhcp11: nic_fr_rx_dsc:    0\n'
                    'zhcp11: nic_fr_rx_err:    0\n'
                    'zhcp11: nic_fr_tx:        16211\n'
                    'zhcp11: nic_fr_tx_dsc:    0\n'
                    'zhcp11: nic_fr_tx_err:    0\n'
                    'zhcp11: nic_rx:           4684435\n'
                    'zhcp11: nic_tx:           3316601\n'
                    'zhcp11: nic_id: INST2 1000\n'
                    'zhcp11: nic_fr_rx:        27211\n'
                    'zhcp11: nic_fr_rx_dsc:    0\n'
                    'zhcp11: nic_fr_rx_err:    0\n'
                    'zhcp11: nic_fr_tx:        12344\n'
                    'zhcp11: nic_fr_tx_dsc:    0\n'
                    'zhcp11: nic_fr_tx_err:    0\n'
                    'zhcp11: nic_rx:           3577163\n'
                    'zhcp11: nic_tx:           2515045\n'
                    'zhcp11: vlan count: 0',
                     None]
        dsh.return_value = {'data': [vsw_data]}
        vsw_dict = zvmutils.virutal_network_vswitch_query_iuo_stats('zhcp11')
        self.assertEqual(2, len(vsw_dict['vswitches']))
        self.assertEqual('INST1',
                         vsw_dict['vswitches'][0]['nics'][0]['userid'])

    @mock.patch.object(zvmutils, 'xdsh')
    def test_virutal_network_vswitch_query_iuo_stats_invalid_data(self, dsh):
        dsh.return_value = ['invalid', 'data']
        self.assertRaises(zvmutils.ZVMException,
                          zvmutils.virutal_network_vswitch_query_iuo_stats,
                          'zhcp')


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
