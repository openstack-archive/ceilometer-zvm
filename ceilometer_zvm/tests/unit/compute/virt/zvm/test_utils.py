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

from ceilometer_zvm.compute.virt.zvm import utils as zvmutils


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
