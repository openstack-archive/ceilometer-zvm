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


import contextlib
import functools
import httplib
import socket

from ceilometer.compute.virt import inspector
from ceilometer.i18n import _
from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class ZVMException(inspector.InspectorException):
    pass


class CacheData(object):
    """Virtual machine stat cache."""
    _CTYPES = ('cpumem', 'vnics')

    def __init__(self):
        self._reset()

    def _reset(self):
        self.cache = dict((tp, {}) for tp in self._CTYPES)

    def set(self, ctype, inst_stat):
        """Set or update cache content.

        @ctype:        cache type.
        @inst_stat:    cache data.
        """
        self.cache[ctype][inst_stat['nodename']] = inst_stat

    def get(self, ctype, inst_name):
        return self.cache[ctype].get(inst_name, None)

    def delete(self, ctype, inst_name):
        if inst_name in self.cache[ctype]:
            del self.cache[ctype][inst_name]

    def clear(self, ctype='all'):
        if ctype == 'all':
            self._reset()
        else:
            self.cache[ctype] = {}


class XCATUrl(object):
    """To return xCAT url for invoking xCAT REST API."""
    def __init__(self):
        self.PREFIX = '/xcatws'
        self.SUFFIX = ''.join(('?userName=', CONF.zvm.zvm_xcat_username,
                               '&password=', CONF.zvm.zvm_xcat_password,
                               '&format=json'))

        # xcat objects
        self.NODES = '/nodes'
        self.TABLES = '/tables'

        # xcat actions
        self.XDSH = '/dsh'

    def _append_addp(self, rurl, addp=None):
        if addp is not None:
            return ''.join((rurl, addp))
        else:
            return rurl

    def xdsh(self, arg=''):
        """Run shell command."""
        return ''.join((self.PREFIX, self.NODES, arg, self.XDSH, self.SUFFIX))

    def gettab(self, arg='', addp=None):
        rurl = ''.join((self.PREFIX, self.TABLES, arg, self.SUFFIX))
        return self._append_addp(rurl, addp)

    def tabdump(self, arg='', addp=None):
        return self.gettab(arg, addp)

    def lsdef_node(self, arg='', addp=None):
        rurl = ''.join((self.PREFIX, self.NODES, arg, self.SUFFIX))
        return self._append_addp(rurl, addp)


class XCATConnection(object):
    """Https requests to xCAT web service."""

    def __init__(self):
        """Initialize https connection to xCAT service."""
        self.host = CONF.zvm.zvm_xcat_server
        self.conn = httplib.HTTPSConnection(self.host,
                                timeout=CONF.zvm.zvm_xcat_connection_timeout)

    def request(self, method, url, body=None, headers={}):
        """Send https request to xCAT server.

        Will return a python dictionary including:
        {'status': http return code,
         'reason': http reason,
         'message': response message}

        """
        if body is not None:
            body = jsonutils.dumps(body)
            headers = {'content-type': 'text/plain',
                       'content-length': len(body)}

        _rep_ptn = ''.join(('&password=', CONF.zvm.zvm_xcat_password))
        LOG.debug("Sending request to xCAT. xCAT-Server:%(xcat_server)s "
                  "Request-method:%(method)s "
                  "URL:%(url)s "
                  "Headers:%(headers)s "
                  "Body:%(body)s" %
                  {'xcat_server': CONF.zvm.zvm_xcat_server,
                   'method': method,
                   'url': url.replace(_rep_ptn, ''),  # hide password in log
                   'headers': str(headers),
                   'body': body})

        try:
            self.conn.request(method, url, body, headers)
        except socket.gaierror as err:
            msg = (_("Failed to connect xCAT server %(srv)s: %(err)s") %
                   {'srv': self.host, 'err': err})
            raise ZVMException(msg)
        except (socket.error, socket.timeout) as err:
            msg = (_("Communicate with xCAT server %(srv)s error: %(err)s") %
                   {'srv': self.host, 'err': err})
            raise ZVMException(msg)

        try:
            res = self.conn.getresponse()
        except Exception as err:
            msg = (_("Failed to get response from xCAT server %(srv)s: "
                     "%(err)s") % {'srv': self.host, 'err': err})
            raise ZVMException(msg)

        msg = res.read()
        resp = {
            'status': res.status,
            'reason': res.reason,
            'message': msg}

        LOG.debug("xCAT response: %s" % str(resp))

        # Only "200" or "201" returned from xCAT can be considered
        # as good status
        err = None
        if method == "POST":
            if res.status != 201:
                err = str(resp)
        else:
            if res.status != 200:
                err = str(resp)

        if err is not None:
            msg = (_('Request to xCAT server %(srv)s failed:  %(err)s') %
                   {'srv': self.host, 'err': err})
            raise ZVMException(msg)

        return resp


def xcat_request(method, url, body=None, headers={}):
    conn = XCATConnection()
    resp = conn.request(method, url, body, headers)
    return load_xcat_resp(resp['message'])


def jsonloads(jsonstr):
    try:
        return jsonutils.loads(jsonstr)
    except ValueError:
        errmsg = _("xCAT response data is not in JSON format")
        LOG.error(errmsg)
        raise ZVMException(errmsg)


@contextlib.contextmanager
def expect_invalid_xcat_resp_data():
    """Catch exceptions when using xCAT response data."""
    try:
        yield
    except (ValueError, TypeError, IndexError, AttributeError,
            KeyError) as err:
        msg = _("Invalid xCAT response data: %s") % str(err)
        raise ZVMException(msg)


def wrap_invalid_xcat_resp_data_error(function):
    """Catch exceptions when using xCAT response data."""

    @functools.wraps(function)
    def decorated_function(*arg, **kwargs):
        try:
            return function(*arg, **kwargs)
        except (ValueError, TypeError, IndexError, AttributeError,
                KeyError) as err:
            msg = _("Invalid xCAT response data: %s") % str(err)
            raise ZVMException(msg)

    return decorated_function


@wrap_invalid_xcat_resp_data_error
def translate_xcat_resp(rawdata, dirt):
    """Translate xCAT response JSON stream to a python dictionary."""
    data_list = rawdata.split("\n")

    data = {}

    for ls in data_list:
        for k in dirt.keys():
            if ls.__contains__(dirt[k]):
                data[k] = ls[(ls.find(dirt[k]) + len(dirt[k])):].strip(' "')
                break

    return data


@wrap_invalid_xcat_resp_data_error
def load_xcat_resp(message):
    """Abstract information from xCAT REST response body."""
    resp_list = jsonloads(message)['data']
    keys = ('info', 'data', 'node', 'errorcode', 'error')

    resp = {}

    for k in keys:
        resp[k] = []

    for d in resp_list:
        for k in keys:
            if d.get(k) is not None:
                resp[k].append(d.get(k))

    err = resp.get('error')
    if err != []:
        for e in err:
            if _is_warning(str(e)):
                # ignore known warnings or errors:
                continue
            else:
                raise ZVMException(message)

    _log_warnings(resp)

    return resp


def _log_warnings(resp):
    for msg in (resp['info'], resp['node'], resp['data']):
        msgstr = str(msg)
        if 'warn' in msgstr.lower():
            LOG.warn(_("Warning from xCAT: %s") % msgstr)


def _is_warning(err_str):
    ignore_list = (
        'Warning: the RSA host key for',
        'Warning: Permanently added',
        'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED',
    )

    for im in ignore_list:
        if im in err_str:
            return True

    return False


def get_userid(node_name):
    """Returns z/VM userid for the xCAT node."""
    url = XCATUrl().lsdef_node(''.join(['/', node_name]))
    info = xcat_request('GET', url)['info']

    with expect_invalid_xcat_resp_data():
        for s in info[0]:
            if s.__contains__('userid='):
                return s.strip().rpartition('=')[2]


def xdsh(node, commands):
    """"Run command on xCAT node."""
    LOG.debug('Run command %(cmd)s on xCAT node %(node)s' %
              {'cmd': commands, 'node': node})

    def xdsh_execute(node, commands):
        """Invoke xCAT REST API to execute command on node."""
        xdsh_commands = 'command=%s' % commands
        body = [xdsh_commands]
        url = XCATUrl().xdsh('/' + node)
        return xcat_request("PUT", url, body)

    res_dict = xdsh_execute(node, commands)

    return res_dict


def get_node_hostname(node_name):
    addp = '&col=node&value=%s&attribute=hostnames' % node_name
    url = XCATUrl().gettab("/hosts", addp)
    with expect_invalid_xcat_resp_data():
        return xcat_request("GET", url)['data'][0][0]


def list_instances(hcp_info):
    zvm_host = CONF.zvm.zvm_host

    url = XCATUrl().tabdump("/zvm")
    res_dict = xcat_request("GET", url)

    instances = {}

    with expect_invalid_xcat_resp_data():
        data_entries = res_dict['data'][0][1:]
        for data in data_entries:
            l = data.split(",")
            node = l[0].strip("\"")
            hcp = l[1].strip("\"")
            userid = l[2].strip("\"")

            # zvm host and zhcp are not included in the list
            if (hcp.upper() == hcp_info['hostname'].upper() and
                    node.upper() not in (zvm_host.upper(),
                    hcp_info['nodename'].upper(),
                    CONF.zvm.zvm_xcat_master.upper())):
                instances[node] = userid.upper()

    return instances


def image_performance_query(zhcp_node, inst_list):
    cmd = ('smcli Image_Performance_Query -T "%(inst_list)s" -c %(num)s' %
           {'inst_list': " ".join(inst_list), 'num': len(inst_list)})

    with expect_invalid_xcat_resp_data():
        resp = xdsh(zhcp_node, cmd)
        raw_data = resp["data"][0][0]

    ipq_kws = {
        'userid': "Guest name:",
        'guest_cpus': "Guest CPUs:",
        'used_cpu_time': "Used CPU time:",
        'used_memory': "Used memory:",
    }

    pi_dict = {}
    with expect_invalid_xcat_resp_data():
        rpi_list = raw_data.split("".join((zhcp_node, ": \n")))
        for rpi in rpi_list:
            pi = translate_xcat_resp(rpi, ipq_kws)
            if pi.get('userid') is not None:
                pi_dict[pi['userid']] = pi

    return pi_dict


def get_inst_name(instance):
    return getattr(instance, 'OS-EXT-SRV-ATTR:instance_name', None)


def get_inst_power_state(instance):
    return getattr(instance, 'OS-EXT-STS:power_state', None)


def virutal_network_vswitch_query_iuo_stats(zhcp_node):
    cmd = ('smcli Virtual_Network_Vswitch_Query_IUO_Stats -T "%s" '
           '-k "switch_name=*"' % zhcp_node)

    with expect_invalid_xcat_resp_data():
        resp = xdsh(zhcp_node, cmd)
        raw_data_list = resp["data"][0]

    while raw_data_list.__contains__(None):
        raw_data_list.remove(None)

    raw_data = '\n'.join(raw_data_list)
    rd_list = raw_data.split('\n')

    def _parse_value(data_list, idx, keyword, offset):
        return idx + offset, data_list[idx].rpartition(keyword)[2].strip()

    vsw_dict = {}
    with expect_invalid_xcat_resp_data():
        # vswitch count
        idx = 0
        idx, vsw_count = _parse_value(rd_list, idx, 'vswitch count:', 2)
        vsw_dict['vswitch_count'] = int(vsw_count)

        # deal with each vswitch data
        vsw_dict['vswitches'] = []
        for i in range(vsw_dict['vswitch_count']):
            vsw_data = {}
            # skip vswitch number
            idx += 1
            # vswitch name
            idx, vsw_name = _parse_value(rd_list, idx, 'vswitch name:', 1)
            vsw_data['vswitch_name'] = vsw_name
            # uplink count
            idx, up_count = _parse_value(rd_list, idx, 'uplink count:', 1)
            # skip uplink data
            idx += int(up_count) * 9
            # skip bridge data
            idx += 8
            # nic count
            vsw_data['nics'] = []
            idx, nic_count = _parse_value(rd_list, idx, 'nic count:', 1)
            nic_count = int(nic_count)
            for j in range(nic_count):
                nic_data = {}
                idx, nic_id = _parse_value(rd_list, idx, 'nic_id:', 1)
                userid, toss, vdev = nic_id.partition(' ')
                nic_data['userid'] = userid
                nic_data['vdev'] = vdev
                idx, nic_data['nic_fr_rx'] = _parse_value(rd_list, idx,
                                                          'nic_fr_rx:', 1)
                idx, nic_data['nic_fr_rx_dsc'] = _parse_value(rd_list, idx,
                                                        'nic_fr_rx_dsc:', 1)
                idx, nic_data['nic_fr_rx_err'] = _parse_value(rd_list, idx,
                                                        'nic_fr_rx_err:', 1)
                idx, nic_data['nic_fr_tx'] = _parse_value(rd_list, idx,
                                                          'nic_fr_tx:', 1)
                idx, nic_data['nic_fr_tx_dsc'] = _parse_value(rd_list, idx,
                                                        'nic_fr_tx_dsc:', 1)
                idx, nic_data['nic_fr_tx_err'] = _parse_value(rd_list, idx,
                                                        'nic_fr_tx_err:', 1)
                idx, nic_data['nic_rx'] = _parse_value(rd_list, idx,
                                                       'nic_rx:', 1)
                idx, nic_data['nic_tx'] = _parse_value(rd_list, idx,
                                                       'nic_tx:', 1)
                vsw_data['nics'].append(nic_data)
            # vlan count
            idx, vlan_count = _parse_value(rd_list, idx, 'vlan count:', 1)
            # skip vlan data
            idx += int(vlan_count) * 3
            # skip the blank line
            idx += 1

            vsw_dict['vswitches'].append(vsw_data)

    return vsw_dict
