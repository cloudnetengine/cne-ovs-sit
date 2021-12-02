# Copyright(c) 2017-2021 CloudNetEngine. All rights reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Defines virtual interface classes."""

from resources.libraries.python.constants import Constants

__all__ = [
    u"InterfaceAddress",
    u"VhostUserInterface",
    u"TapInterface",
]

class InterfaceAddress():
    """Define interface address."""
    def __init__(self, ipv4, ipv4_network, ipv6, ipv6_network):
        self.ipv4 = ipv4
        self.ipv4_network = ipv4_network
        self.ipv6 = ipv6
        self.ipv6_network = ipv6_network

    def ipv4_str_with_prefix(self):
        """Return string contains ipv4 address and prefix.
        """
        return f"{self.ipv4}/{self.ipv4_network.prefixlen}"

    def ipv6_str_with_prefix(self):
        """Return string contains ipv6 address and prefix.
        """
        return f"{self.ipv6}/{self.ipv6_network.prefixlen}"

class VirtualInterface():
    """Define virtual interface base class."""
    def __init__(self, name, idx, mac, ofp):
        self.name = name
        self.idx = idx
        self.mac = mac
        self.ofp = ofp
        self.if_addr = None
        self.restore_if_addr = None
        self.vni = Constants.VNI_NONE
        self.offload = True

    def has_same_subnet(self, vif):
        """Compare two VIFs subnet.
        """
        # vif's ipv4 and ipv6 must have the same reachability attribute
        if self.if_addr.ipv4_network.compare_networks(vif.if_addr.ipv4_network) != 0:
            return False
        return True

class VhostUserInterface(VirtualInterface):
    """Define vhost user interface class."""
    def __init__(self, name, idx, mac, ofp):
        super().__init__(name, idx, mac, ofp)
        self.sock = None
        self.qemu_option = ''
        self.qpair = 1
        self.backend_client_mode = True
        self.qemu_script_ifup = None
        self.qemu_script_ifdown = None

class TapInterface(VirtualInterface):
    """Define TAP interface class."""
    def __init__(self, name, ofp):
        super().__init__(name, None, None, ofp)
