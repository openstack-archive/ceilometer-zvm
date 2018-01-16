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

from ceilometer_zvm.compute.virt.zvm import exception
from ceilometer_zvm.compute.virt.zvm import utils as zvmutils
from zvmconnector import connector


class TestZVMUtils(unittest.TestCase):

    def setUp(self):
        super(TestZVMUtils, self).setUp()
        self._inst = mock.MagicMock()
        setattr(self._inst, 'OS-EXT-SRV-ATTR:instance_name',
                'fakeinst')
        setattr(self._inst, 'OS-EXT-STS:power_state',
                0x01)

    def test_get_instance_name(self):
        inst = zvmutils.get_inst_name(self._inst)
        self.assertEqual('fakeinst', inst)

    def test_get_inst_power_state(self):
        pst = zvmutils.get_inst_power_state(self._inst)
        self.assertEqual(0x01, pst)


class TestZVMConnectorRequestHandler(unittest.TestCase):

    @mock.patch.object(connector.ZVMConnector, '__init__')
    def test_init_with_http(self, connector_init):
        connector_init.return_value = None
        conf = mock.Mock()
        conf.zvm_cloud_connector_url = 'http://1.1.1.1:1111'
        conf.zvm_cloud_connector_token_file = '/tmp/token.txt'
        zvmutils.zVMConnectorRequestHandler(conf)
        connector_init.assert_called_once_with('1.1.1.1', 1111,
                                               ssl_enabled=False,
                                               token_path='/tmp/token.txt',
                                               verify=False)

    @mock.patch.object(connector.ZVMConnector, '__init__')
    def test_init_with_https_insecure(self, connector_init):
        connector_init.return_value = None
        conf = mock.Mock()
        conf.zvm_cloud_connector_url = 'https://1.1.1.1:1111'
        conf.zvm_cloud_connector_token_file = '/tmp/token.txt'
        conf.zvm_cloud_connector_ca_file = None
        zvmutils.zVMConnectorRequestHandler(conf)
        connector_init.assert_called_once_with('1.1.1.1', 1111,
                                               ssl_enabled=True,
                                               token_path='/tmp/token.txt',
                                               verify=False)

    @mock.patch.object(connector.ZVMConnector, '__init__')
    def test_init_with_https_secure(self, connector_init):
        connector_init.return_value = None
        conf = mock.Mock()
        conf.zvm_cloud_connector_url = 'https://1.1.1.1:1111'
        conf.zvm_cloud_connector_token_file = '/tmp/token.txt'
        conf.zvm_cloud_connector_ca_file = '/tmp/ca.pem'
        zvmutils.zVMConnectorRequestHandler(conf)
        connector_init.assert_called_once_with('1.1.1.1', 1111,
                                               ssl_enabled=True,
                                               token_path='/tmp/token.txt',
                                               verify='/tmp/ca.pem')

    @mock.patch.object(connector.ZVMConnector, 'send_request')
    def test_call(self, send_request):
        send_request.return_value = {"overallRC": 0, 'output': "OK"}
        conf = mock.Mock()
        conf.zvm_cloud_connector_url = 'http://1.1.1.1:1111'
        conf.zvm_cloud_connector_token_file = '/tmp/token.txt'
        req_handler = zvmutils.zVMConnectorRequestHandler(conf)
        info = req_handler.call('API', "parm1", "parm2")
        send_request.assert_called_with('API', "parm1", "parm2")
        self.assertEqual("OK", info)

    @mock.patch.object(connector.ZVMConnector, 'send_request')
    def test_call_exception(self, send_request):
        conf = mock.Mock()
        conf.zvm_cloud_connector_url = 'http://1.1.1.1:1111'
        conf.zvm_cloud_connector_token_file = '/tmp/token.txt'
        req_handler = zvmutils.zVMConnectorRequestHandler(conf)
        send_request.return_value = {"overallRC": 1, 'output': ""}
        self.assertRaises(exception.ZVMConnectorRequestFailed,
                          req_handler.call,
                          "API")
