# Copyright 2012 OpenStack Foundation
# All Rights Reserved.
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


import cStringIO
import select
import six
import socket
import time
import warnings

from tempest import exceptions
from tempest.openstack.common import log as logging


with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import paramiko


LOG = logging.getLogger(__name__)


class Client(object):

    def __init__(self, host, username, password=None, timeout=300, pkey=None,
                 channel_timeout=10, look_for_keys=False, key_filename=None,
                 use_gw=False, gateway=None, gw_port=None, gw_password=None,
                 gw_username=None, gw_key_filename=None, gw_pkey=None):
        self.host = host
        self.username = username
        self.password = password
        if isinstance(pkey, six.string_types):
            pkey = paramiko.RSAKey.from_private_key(
                cStringIO.StringIO(str(pkey)))
        self.pkey = pkey
        self.look_for_keys = look_for_keys
        self.key_filename = key_filename
        self.timeout = int(timeout)
        self.channel_timeout = float(channel_timeout)
        self.buf_size = 1024
        self.use_gw = use_gw
        self.gateway = gateway
        self.gw_port = gw_port
        self.gw_password = gw_password
        self.gw_username = gw_username
        self.gw_key_filename = gw_key_filename
        if gw_pkey is not None and isinstance(gw_pkey, six.string_types):
            gw_pkey = paramiko.RSAKey.from_private_key(
                cStringIO.StringIO(str(gw_pkey)))
        self.gw_pkey = gw_pkey
        self.gw_ssh = None

    def _get_ssh_connection(self, sleep=1.5, backoff=1):
        """Returns an ssh connection to the specified host."""
        bsleep = sleep
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy())

        _start_time = time.time()
        if self.pkey is not None:
            LOG.info("Creating ssh connection to '%s' as '%s'"
                     " with public key authentication",
                     self.host, self.username)
        else:
            LOG.info("Creating ssh connection to '%s' as '%s'"
                     " with password %s",
                     self.host, self.username, str(self.password))
        attempts = 0
        while True:
            try:
                if self.use_gw:

                    self.ssh_gw = paramiko.SSHClient()
                    self.ssh_gw.set_missing_host_key_policy(
                    paramiko.AutoAddPolicy())


                    self.ssh_gw.connect(self.gateway, username=self.gw_username,
                                password=self.gw_password,
                                look_for_keys=self.look_for_keys,
                                key_filename=self.gw_key_filename,
                                timeout=self.channel_timeout, pkey=self.gw_pkey)

                    LOG.info("ssh connection to %s@%s successfuly created",
                         self.gw_username, self.gateway)

                    transport = self.ssh_gw.get_transport()
                    dest_addr = (self.host, 22)
                    local_addr = ('127.0.0.1', 4000)
                    channel = transport.open_channel("direct-tcpip", dest_addr, local_addr)

                    LOG.info('Connecting through the tunnel')
                    ssh.connect(hostname='localhost', username=self.username,
                                password=self.password, port=4000,
                                look_for_keys=self.look_for_keys,
                                key_filename=self.key_filename,
                                timeout=self.channel_timeout,
                                pkey=self.pkey, sock=channel)
                else:

                    ssh.connect(self.host, username=self.username,
                            password=self.password,
                            look_for_keys=self.look_for_keys,
                            key_filename=self.key_filename,
                            timeout=self.channel_timeout, pkey=self.pkey)

                LOG.info("ssh connection to %s@%s successfuly created",
                         self.username, self.host)

                return ssh
            except (socket.error,
                    paramiko.SSHException) as e:
                if self._is_timed_out(_start_time):
                    LOG.exception("Failed to establish authenticated ssh"
                                  " connection to %s@%s after %d attempts",
                                  self.username, self.host, attempts)
                    raise exceptions.SSHTimeout(host=self.host,
                                                user=self.username,
                                                password=self.password)
                bsleep += backoff
                attempts += 1
                LOG.warning("Failed to establish authenticated ssh"
                            " connection to %s@%s (%s). Number attempts: %s."
                            " Retry after %d seconds.",
                            self.username, self.host, e, attempts, bsleep)
                time.sleep(bsleep)

    def _is_timed_out(self, start_time, timeout=0):
        if timeout is 0:
            timeout = self.timeout
        return (time.time() - timeout) > start_time

    def exec_command(self, cmd, cmd_timeout=0):
        """
        Execute the specified command on the server.

        Note that this method is reading whole command outputs to memory, thus
        shouldn't be used for large outputs.

        :returns: data read from standard output of the command.
        :raises: SSHExecCommandFailed if command returns nonzero
                 status. The exception contains command status stderr content.
        """
        ssh = self._get_ssh_connection()
        transport = ssh.get_transport()
        channel = transport.open_session()
        channel.fileno()  # Register event pipe
        channel.exec_command(cmd)
        channel.shutdown_write()
        out_data = []
        err_data = []
        poll = select.poll()
        poll.register(channel, select.POLLIN)
        start_time = time.time()

        while True:
            ready = poll.poll(self.channel_timeout)
            if not any(ready) or cmd_timeout is not 0:
                if not self._is_timed_out(start_time, cmd_timeout):
                    continue
                raise exceptions.TimeoutException(
                    "Command: '{0}' executed on host '{1}'.".format(
                        cmd, self.host))
            if not ready[0]:  # If there is nothing to read.
                continue
            out_chunk = err_chunk = None
            if channel.recv_ready():
                out_chunk = channel.recv(self.buf_size)
                out_data += out_chunk,
            if channel.recv_stderr_ready():
                err_chunk = channel.recv_stderr(self.buf_size)
                err_data += err_chunk,
            if channel.closed and not err_chunk and not out_chunk:
                break
        exit_status = channel.recv_exit_status()
        if 0 != exit_status:
            raise exceptions.SSHExecCommandFailed(
                command=cmd, exit_status=exit_status,
                strerror=''.join(err_data))
        return ''.join(out_data)

    def test_connection_auth(self):
        """Raises an exception when we can not connect to server via ssh."""
        connection = self._get_ssh_connection()
        connection.close()
