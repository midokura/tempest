import subprocess
import shlex

class Routetable:

    def __init__(cls, *args):
        cls.destination = None
        cls.gateway = None
        cls.genmask = None
        cls.flags = None
        cls.metric = None
        cls.ref = None
        cls.use = None
        cls.iface = None
        if len(args) is 1:
            cls.init_from_line(args[0])
            return

        (cls.destination, cls.gateway, cls.iface) = args
        if len(args) > 3:
            cls.genmask = args[3]

    def init_from_line(self, line):
        """
        default         10.10.1.1       0.0.0.0         U     0      0      0       eth0
        """
        cols = line.split(None)
        try:
            if len(cols) < 8 or not cols or cols[0] is "Destination":
                self.destination = None
                return
            self.destination = cols[0]
            self.gateway = cols[1]
            self.genmask = cols[2]
            self.flags = cols[3]
            self.metric = cols[4]
            self.ref = cols[5]
            self.use = cols[6]
            self.iface = cols[7]
        except Exception as error:
            raise error

    def __repr__(self):
        """Return a string representing the route"""
        return "dest=%-16s gw=%-16s mask=%-16s use=%s iface=%s" % (self.destination,
                                                            self.gateway,
                                                            self.genmask,
                                                            self.use,
                                                            self.iface)

    def is_default_route(self):
        if self.destination is "default" or "0.0.0.0" and self.flags is "UGS" or "UC":
            return True


    @staticmethod
    def build_route_table(route_output):
        """
        ***Builds a route table from the route command output:***
        Kernel IP routing table
        Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
        default         10.10.1.1       0.0.0.0         U     0      0        0 eth0
        10.10.1.0       *               255.255.255.0   U     0      0        0 eth0
        """
        rtable = []
        lines = route_output.split("\n")
        for line in lines[2:]:
            r = Routetable(line)
            if r.destination:
                rtable.append(r)

        return rtable


class SSHTunnel:

    #ssh -L 4000:10.10.1.2:22 cirros@200.200.200.179
    def __init__(cls, username="cirros", destination="10.10.1.2",
                  gateway="200.200.200.179", localport=4000, remotePort=22):
        cls.username = username
        cls.destination = destination
        cls.gateway = gateway
        cls.localport = localport
        cls.remotePort = remotePort
        cls.tunnel = None

    def _check_gateway_reachability(self):
        cmd = "ping -c1 -w1 %s" % self.gateway
        args = shlex.split(cmd)
        ping = subprocess.call(args)
        if ping is not 0:
            return False
        return True

    def build_tunnel(self):
        cmd = "ssh -L {0}:{1}:{2} {3}@{4}".format(self.localport, self.destination, self.remotePort,
                                                  self.username, self.gateway)
        args = shlex.split(cmd)
        self.tunnel = subprocess.Popen(args, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.setNonBlocking(self.tunnel.stdout)
        subprocess.setNonBlocking(self.tunnel.stderr)

        while True:
            try:
                output = self.tunnel.stdout.read()
            except IOError:
                continue
            else:
                break


    def __del__(self):
        self.tunnel.kill()
