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

