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

    if data == {}:
        msg = _("No value matched with keywords. Raw Data: %(raw)s; "
                "Keywords: %(kws)s") % {'raw': rawdata, 'kws': str(dirt)}
        raise ZVMException(msg)

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
