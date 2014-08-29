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
import random
import select
import six
import socket
import time
import warnings

from tempest import exceptions
from tempest.openstack.common import log as logging
from pprint import pprint

try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import paramiko


LOG = logging.getLogger(__name__)


class Client(SocketServer.BaseRequestHandler):

    def __init__(self, host, username, password=None, timeout=300, pkey=None,
                 channel_timeout=10, look_for_keys=False, key_filename=None,
                 gws=[]):
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

        #GW stuff
        self.GWs = gws
        self.tunnels = []
        self.ssh_gw = None

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
                if self.GWs:
                    ssh = self._build_tunnel()
                else:

                    ssh.connect(self.host, username=self.username,
                            password=self.password,
                            look_for_keys=self.look_for_keys,
                            key_filename=self.key_filename,
                            timeout=self.channel_timeout, pkey=self.pkey)

                LOG.info("ssh connection to %s@%s successfully created",
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

    def _build_tunnel(self):
        """
         Builds a ssh inception tunneling with through GW added tot he list of GWs
         This function needs a refactor!!
        """
        ssh_gw = paramiko.SSHClient()
        ssh_gw.set_missing_host_key_policy(
             paramiko.AutoAddPolicy())

        gw = self.GWs[0]

        if isinstance(gw["pkey"], six.string_types):
            gw["pkey"] = paramiko.RSAKey.from_private_key(
            cStringIO.StringIO(str(gw["pkey"])))

        ssh_gw.connect(gw["ip"], username=gw["username"],
                                password=gw["password"],
                                look_for_keys=self.look_for_keys,
                                key_filename=gw["key_filename"],
                                timeout=self.channel_timeout, pkey=gw["pkey"])

        self.tunnels.append(ssh_gw)

        for dest in self.GWs[1:]:
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(
                    paramiko.AutoAddPolicy())

                if isinstance(dest["pkey"], six.string_types):
                    dest["pkey"] = paramiko.RSAKey.from_private_key(
                    cStringIO.StringIO(str(dest["pkey"])))

                transport = self.tunnels[-1].get_transport()
                dest_addr = (dest["ip"], 22)
                local_addr = ('127.0.0.1', self._get_local_unused_tcp_port())
                channel = transport.open_channel("direct-tcpip", dest_addr, local_addr)

                LOG.info('Connecting through the tunnel')
                ssh.connect(hostname='localhost', username=dest["username"],
                            password=dest["password"],
                            look_for_keys=self.look_for_keys,
                            key_filename=dest["key_filename"],
                            timeout=self.channel_timeout,
                            pkey=dest["pkey"], sock=channel)

                LOG.info("Tunnel connection %s@%s successfully created through localhost port:4000",
                                     self.username, self.host)
                self.tunnels.append(ssh)
            except (socket.error,
                    paramiko.SSHException):
                    raise

        self.ssh_gw = self.tunnels[-1]

        try:
            transport = self.ssh_gw.get_transport()
            dest_addr = (self.host, 22)
            local_addr = ('127.0.0.1', self._get_local_unused_tcp_port())
            channel = transport.open_channel("direct-tcpip", dest_addr, local_addr)

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(
                    paramiko.AutoAddPolicy())
            LOG.info('Connecting through the tunnel')
            ssh.connect(hostname='localhost', username=self.username,
                        password=self.password,
                        look_for_keys=self.look_for_keys,
                        key_filename=self.key_filename,
                        timeout=self.channel_timeout,
                        pkey=self.pkey, sock=channel)
            return ssh
        except (socket.error,
                    paramiko.SSHException):
                    raise
        raise Exception("something went extremely wrong")

    def _is_timed_out(self, start_time, timeout=0):
        if timeout is 0:
            timeout = self.timeout
        return (time.time() - timeout) > start_time

    @staticmethod
    def _get_local_unused_tcp_port():
        port = random.randrange(10000, 65535)
        s = socket.socket()
        attempts = 0
        while attempts < 10:
            try:
                LOG.info("is port %d free?" % port)
                s.connect(('127.0.0.1', port))
                s.shutdown()

                LOG.info("port %d is not free" % port)
                attempts += 1
            except:
                # port is unused
                LOG.info("port %d is free" % port)
                return port

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
        LOG.info("executing cmd: %s" % cmd)
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
            #LOG.info("error %s" % err_data)
            #LOG.info("out %s" % out_data)
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
