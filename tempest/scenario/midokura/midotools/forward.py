#!/usr/bin/env python

# Copyright (C) 2008  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Sample script showing how to do remote port forwarding over paramiko.

This script connects to the requested SSH server and sets up remote port
forwarding (the openssh -R option) from a remote port through a tunneled
connection to a destination reachable from the local machine.
"""

import getpass
import os
import socket
import select
import sys
import threading
from pprint import pprint
from optparse import OptionParser

import paramiko


class Forward(object):

    SSH_PORT = None
    DEFAULT_PORT = None
    g_verbose = None

    def __int__(self):
        self.SSH_PORT = 22
        self.DEFAULT_PORT = 4000
        self.g_verbose = True

    def _handler(self, chan, host, port):
        sock = socket.socket()
        try:
            sock.connect((host, port))
        except Exception as e:
            self._verbose('Forwarding request to %s:%d failed: %r' % (host, port, e))
            return

        self._verbose('Connected!  Tunnel open %r -> %r -> %r' % (chan.origin_addr,
                                                                chan.getpeername(),
                                                                (host, port)))
        while True:
            r, w, x = select.select([sock, chan], [], [])
            if sock in r:
                data = sock.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                sock.send(data)
        chan.close()
        sock.close()
        self._verbose('Tunnel closed from %r' % (chan.origin_addr,))


    def _reverse_forward_tunnel(self, server_port, remote_host, remote_port, transport):
        transport.request_port_forward('', server_port)
        while True:
            chan = transport.accept(1000)
            if chan is None:
                continue
            thr = threading.Thread(target=self._handler, args=(chan, remote_host, remote_port))
            thr.setDaemon(True)
            thr.start()

    def _verbose(self, s):
        if self.g_verbose:
            print(s)

    def build_tunnel(self, options, server_ip, remote_ip):
        #options, server, remote = parse_options()
        """
        :param options: {verbose: True, user: getpass.getuser(), keyfile: None, password: None, look_for_keys=True }
        :param server: (server_host, server_port)
        :param remote: (remote_host, remote_port)
        :return:
        """

        server = (server_ip, self.SSH_PORT)
        remote = (remote_ip, self.SSH_PORT)

        #should be mandatory for cirros?
        pprint(options)
        if options.password:
            password = options.password
        #if options.readpass:
        #    password = getpass.getpass('Enter SSH password: ')

        client = paramiko.SSHClient()
        #do I need this? how to integrate it with our system/tempest ?
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy())

        self._verbose('Connecting to ssh host %s:%d ...' % (server[0], server[1]))
        try:
            client.connect(server[0], server[1], username=options.user, key_filename=options.keyfile,
                           look_for_keys=options.look_for_keys, password=password)
        except Exception as e:
            print('*** Failed to connect to %s:%d: %r' % (server[0], server[1], e))
            sys.exit(1)

        self._verbose('Now forwarding remote port %d to %s:%d ...' % (options.port, remote[0], remote[1]))

        try:
            self._reverse_forward_tunnel(options.port, remote[0], remote[1], client.get_transport())
        except KeyboardInterrupt:
            print('C-c: Port forwarding stopped.')
            sys.exit(0)


