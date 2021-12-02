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

"""Defines keywords for virtual switch operations."""

import os
import re

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn

from resources.libraries.python.constants import Constants
from resources.libraries.python.ssh import exec_cmd, kill_process
from resources.libraries.python.vif import TapInterface

__all__ = [
    u"VirtualSwitch",
    u"OvsDpdk",
    u"OvsNative",
    u"Uplink",
    u"TunnelPort",
]

class Uplink():
    """Contains uplink configuration. """
    def __init__(self, pci_addr):
        self.pci_addr = pci_addr
        self.name = None # Uplink's name is populated during start_vswitch
        self.ofp = None # uplink's ofp is populated when it's added to a bridge
        self.n_queue_pair = None
        self.n_rxq_desc = None
        self.n_txq_desc = None

class TunnelPort():
    """Contains tunnel port configuration. """
    def __init__(self, name, rip, vni, ofp):
        self.name = name
        self.rip = rip
        self.vni = vni
        self.ofp = ofp

class IDAllocator():
    """Allocator for managing IDs. """
    def __init__(self, name, min_id, max_id):
        self.name = name
        self.ids = list(range(min_id, max_id+1))

    def get(self):
        """Get an ID from the allocator.
        returns: An ID.
        rtype: int
        """
        get_id = self.ids.pop(0)
        return get_id

    def put(self, put_id):
        """Put an ID back to the allocator.
        param put_id: ID to put back.
        type put_id: int
        """
        self.ids.append(put_id)

class Bridge():
    """Contains bridge configuration. """
    def __init__(self, name):
        self.name = name
        self.vifs = list()
        self.vnis = dict()
        self.uplinks = list()
        self.tnl_ports = list()
        self.with_md = False
        self.ofp_ids_uplink = IDAllocator(f"{name} uplink", Constants.OFP_UPLINK_BASE,
                                          Constants.OFP_VHOST_BASE)
        self.ofp_ids_vif = IDAllocator(f"{name} vif", Constants.OFP_VHOST_BASE,
                                       Constants.OFP_TUNNEL_BASE)
        self.ofp_ids_tunnel = IDAllocator(f"{name} tunnel", Constants.OFP_TUNNEL_BASE,
                                          Constants.OFP_TUNNEL_BASE+100)

def _bridge_add_vni(br, vif):
    if not vif.vni in br.vnis:
        br.vnis[vif.vni] = list()
    br.vnis[vif.vni].append(vif)

def _bridge_add_vif(br, vif):
    br.vifs.append(vif)
    _bridge_add_vni(br, vif)


class VirtualSwitch():
    """Defines basic methods and attirbutes of a virtual switch."""
    def __init__(self, ssh_info, uplinks_spec, tep_addr, ovs_bin_dir, dpdk_devbind_dir):
        self.bridges = list()
        self.ssh_info = ssh_info
        self.tep_addr = tep_addr

        # Sorted uplink interface based on interface pseudo name in config file
        self.uplinks = list()
        self.bound_uplinks = list()
        iface_keys = sorted(uplinks_spec.keys())
        for iface in iface_keys:
            iface_spec = uplinks_spec[iface]
            uplink = Uplink(iface_spec['pci_address'])
            if iface_spec.get("n_queue_pair"):
                uplink.n_queue_pair = iface_spec.get("n_queue_pair")
            if iface_spec.get("n_rxq_desc"):
                uplink.n_rxq_desc = iface_spec.get("n_rxq_desc")
            if iface_spec.get("n_txq_desc"):
                uplink.n_txq_desc = iface_spec.get("n_txq_desc")
            self.uplinks.append(uplink)

        self._ovs_bin_dir = ovs_bin_dir
        self._dpdk_devbind_full_cmd = os.path.join(dpdk_devbind_dir, "dpdk-devbind.py")

    def execute(self, cmd, timeout=30):
        """Execute an OVS command.

        :param cmd: OVS command.
        :param timeout: Timeout value in seconds.
        :type cmd: str
        :type timeout: int
        :returns: ret_code, stdout, stderr
        :rtype: tuple(int, str, str)
        """
        ret_code, stdout, stderr = \
            exec_cmd(self.ssh_info, f"{self._ovs_bin_dir}/{cmd}", timeout, sudo=True)
        logger.trace(stdout)

        if ret_code is None or int(ret_code) != 0:
            raise RuntimeError(f"Execute OVS cmd failed on {self.ssh_info['host']} : {cmd}")

        return (ret_code, stdout, stderr)

    def execute_batch(self, cmds, timeout=30):
        """Execute a batch of OVS commands.

        :param cmds: OVS commands.
        :param timeout: Timeout value in seconds.
        :type cmds: list(str)
        :type timeout: int
        """
        for cmd in cmds:
            self.execute(cmd, timeout)

    def execute_host(self, cmd, timeout=30, exp_fail=False):
        """Execute a command on a host which the vswitch resides.

        :param cmd: Command.
        :param timeout: Timeout value in seconds.
        :param exp_fail: Expect the command failure or success. Default: False.
                         None means don't care about the command result.
        :type cmd: str
        :type timeout: int
        :type exp_fail: bool
        :returns: ret_code, stdout, stderr
        :rtype: tuple(int, str, str)
        """
        ret_code, stdout, stderr = \
            exec_cmd(self.ssh_info, cmd, timeout, sudo=True)
        logger.trace(stdout)

        if ret_code is None or int(ret_code) != 0:
            # 'None' for exp_fail means don't care the result
            if exp_fail is not None and not exp_fail:
                raise RuntimeError(f"Execute host cmd failed on {self.ssh_info['host']} : {cmd}")

        return (ret_code, stdout, stderr)

    def execute_host_batch(self, cmds, timeout=30):
        """Execute a batch of commands on a host which the vswitch resides.

        :param cmds: Commands.
        :param timeout: Timeout value in seconds.
        :type cmds: list(str)
        :type timeout: int
        """
        for cmd in cmds:
            self.execute_host(cmd, timeout)

    def kill_process(self, proc_name):
        """Kill a process on a host which the vswitch resides.

        :param proc_name: Process name.
        :type proc_name: str
        """
        kill_process(self.ssh_info, proc_name)

    def get_bridge(self, br_name):
        """Get a Bridge object by a bridge name.

        :param br_name: Bridge name.
        :type br_name: str
        :returns: Bridge object.
        :rtype: Bridge obj
        """
        for br in self.bridges:
            if br.name == br_name:
                return br
        return None

    def _create_bridge_impl(self, br):
        """Get a Bridge object by a bridge name.

        :param br_name: Bridge name.
        :type br_name: str
        :returns: Bridge object.
        :rtype: Bridge obj
        """

    def create_bridge(self, br_name):
        """Create an OVS bridge.

        :param br_name: Bridge name.
        :type br_name: str
        :returns: Bridge object.
        :rtype: Bridge obj
        """
        # There might be stale tap interface left on the host if the previous
        # run is not gracefully exit, just try to delete it.
        self.execute_host(f"ip link del {br_name}", exp_fail=None)
        br = Bridge(br_name)
        self._create_bridge_impl(br)
        self.bridges.append(br)
        tap = TapInterface(br_name, Constants.OFP_LOCAL)
        _bridge_add_vif(br, tap)
        return br

    def delete_bridge(self, br_name):
        """Delete an OVS bridge.

        :param br_name: Bridge name.
        :type name: str
        """
        self.execute('ovs-vsctl del-br {}'.format(br_name))
        br = self.get_bridge(br_name)
        self.bridges.remove(br)

    def refresh_bridge_vnis(self):
        """Refresh vni -> vif maps of all bridges on the virtual switch. """
        for br in self.bridges:
            br.vnis = dict()
            for vif in br.vifs:
                _bridge_add_vni(br, vif)

    def create_tunnel_port(self, br_name, tnl_type, rip, vni):
        """Create a tunnel port on a bridge.

        :param br_name: Bridge name.
        :param tnl_type: Tunnel type.
        :param rip: Tunnel remote ip.
        :param vni: Virtual network identifier.
        :type br_name: str
        :type tnl_type: str
        :type rip: IPv4Address or IPv6Address or 'flow'
        :type vni: int or 'flow'
        :returns: Tunnel port.
        :rtype: TunnelPort obj
        """
        br = self.get_bridge(br_name)
        tnl_ofp = br.ofp_ids_tunnel.get()

        tnl_name = '{0}{1}'.format(tnl_type, tnl_ofp)
        self.execute(f"ovs-vsctl add-port {br_name} {tnl_name} "
                     f"-- set Interface {tnl_name} type={tnl_type} "
                     f"options:remote_ip={rip} "
                     f"options:key={vni} ofport_request={tnl_ofp} ")
        tnl_port = TunnelPort(tnl_name, rip, vni, tnl_ofp)
        br = self.get_bridge(br_name)
        br.tnl_ports.append(tnl_port)
        return tnl_port

    def delete_tunnel_port(self, br_name, tnl_port):
        """Delete a tunnel port from a bridge.

        :param br_name: Bridge name.
        :param tnl_port: Tunnel port.
        :type br_name: str
        :type tnl_port: TunnelPort obj
        """
        br = self.get_bridge(br_name)
        self.delete_interface(br_name, tnl_port.name)
        br.ofp_ids_tunnel.put(tnl_port.ofp)
        br.tnl_ports.remove(tnl_port)

    def _create_vhost_user_interface_impl(self, br_name, vif):
        """Create a vhost user interface on a bridge.

        :param br_name: Bridge name.
        :param vif: Virtual interface.
        :type br_name: str
        :type vif: VirtualInterface obj
        """

    def _create_uplink_interface_impl(self, br_name, uplink):
        """Create an uplink interface on a bridge.

        :param node: Node to create interface on.
        :param br_name: Bridge name.
        :param if_name: Interface name.
        :type node: dict
        :type br_name: str
        :type if_name: str
        """

    def delete_interface(self, br_name, if_name):
        """Delete an interface on CNE vSwitch.

        :param node: Node to create interface on.
        :param br_name: Bridge name.
        :param if_name: Interface name.
        :type node: dict
        :type br_name: str
        :type if_name: str
        :return: Operation status.
        :rtype: int
        """

        self.execute(f"ovs-vsctl del-port {br_name} {if_name}")
    def set_port_vlan(self, if_name, vlan_id):
        """Delete an interface on CNE vSwitch.

        :param node: Node to create interface on.
        :param br_name: Bridge name.
        :param if_name: Interface name.
        :type node: dict
        :type br_name: str
        :type if_name: str
        :return: Operation status.
        :rtype: int
        """
        self.execute(f"ovs-vsctl set port {if_name} tag={vlan_id}")

    def set_vlan_limit(self, limit):
        """Set VLAN limit of a virtual switch.

        :param limit: VLAN limitation.
        :type limit: int
        """
        self.execute(f"ovs-vsctl set Open_vSwitch . other_config:vlan-limit={limit}")

    def set_uplink_mtu(self, mtu=1600):
        """Set uplink MTU.

        :param mtu: Request MTU.
        :type mtu: int
        """
        for br in self.bridges:
            for uplink in br.uplinks:
                self.execute(f"ovs-vsctl set Interface {uplink.name} mtu_request={mtu}")

    def create_vhost_user_interface(self, br_name, vif):
        """Create a vhost user interface on a bridge.

        :param node: Node to create interface on.
        :param br_name: Bridge name.
        :param if_name: Interface name.
        :type node: dict
        :type br_name: str
        :type vif: dict
        """
        self._create_vhost_user_interface_impl(br_name, vif)
        br = self.get_bridge(br_name)
        _bridge_add_vif(br, vif)

    def _create_uplink_bond_impl(self, br):
        pass

    def create_uplink_bridge(self, br_name, bond=False):
        """Create an OVS bridge with uplinks.
        It will also bind tep network configuration on the bridge local port.

        :param br_name: Bridge name.
        :param bond: Configure bond or not.
        :type br_name: str
        :type bond: bool
        """
        br = self.create_bridge(br_name)
        ipv4_str = self.tep_addr.ipv4_str_with_prefix()
        ipv6_str = self.tep_addr.ipv6_str_with_prefix()
        cmds = [f"ip -4 addr add {ipv4_str} dev {br_name}",
                f"ip -6 addr add {ipv6_str} dev {br_name}",
                f"ip link set {br_name} up",
                f"ip -4 route flush {self.tep_addr.ipv4_network}",
                f"ip -6 route flush {self.tep_addr.ipv6_network}",
                f"ip -4 route add {self.tep_addr.ipv4_network} dev {br_name}",
                f"ip -6 route add {self.tep_addr.ipv6_network} dev {br_name}"]
        self.execute_host_batch(cmds)

        if not bond:
            self.uplinks[0].ofp = Constants.OFP_UPLINK_BASE
            self._create_uplink_interface_impl(br_name, self.uplinks[0])
            br.uplinks.append(self.uplinks[0])
            return

        self._create_uplink_bond_impl(br)

    def _delete_uplink_impl(self, uplink):
        pass

    def delete_uplink_bridge(self, br_name):
        """Delete an uplink bridge.

        :param br_name: Bridge name.
        :type br_name: str
        """
        br = self.get_bridge(br_name)
        for uplink in br.uplinks:
            self._delete_uplink_impl(uplink)
            uplink.ofp = None
        self.delete_bridge(br_name)

    def _set_bond_member_up_impl(self, if_name, up=True):
        pass

    def set_bond_member_up(self, br_name, idx, up=True):
        """Bring bond member up or down.

        :param br_name: Bridge name.
        :param idx: Uplink index.
        :param up: Up or down.
        :type br_name: str
        :type idx: int
        :type up: bool
        """
        if up:
            self.execute(f"ovs-ofctl mod-port {br_name} {self.uplinks[idx].name} up")
        else:
            self.execute(f"ovs-ofctl mod-port {br_name} {self.uplinks[idx].name} down")
        self._set_bond_member_up_impl(self.uplinks[idx].name, up)

    def start_vswitch(self):
        """Start a virtual switch. """

    def stop_vswitch(self):
        """Stop a virtual switch. """
        self.kill_process("ovs-vswitchd")
        self.kill_process("ovsdb-server")

class OvsDpdk(VirtualSwitch):
    """Methods for OVS-DPDK virtual switch. """
    def __init__(self, ssh_info, uplinks_spec, tep_ipv4, ovs_bin_dir, dpdk_devbind_dir, aux_params):
        super().__init__(ssh_info, uplinks_spec, tep_ipv4, ovs_bin_dir, dpdk_devbind_dir)
        self._aux_params = aux_params

    def _create_bridge_impl(self, br):
        self.execute(f"ovs-vsctl add-br {br.name} " \
                     f"-- set bridge {br.name} datapath_type=netdev")

    def _create_vhost_user_interface_impl(self, br_name, vif):
        if vif.backend_client_mode:
            self.execute(f"ovs-vsctl add-port {br_name} {vif.name} "
                         f"-- set Interface {vif.name} type=dpdkvhostuserclient "
                         f"options:vhost-server-path={vif.sock} "
                         f"ofport_request={vif.ofp}")
        else:
            self.execute(f"ovs-vsctl add-port {br_name} {vif.name} "
                         f"-- set Interface {vif.name} type=dpdkvhostuser "
                         f"ofport_request={vif.ofp}")

    def _create_uplink_interface_impl(self, br_name, uplink):
        options = ''
        if uplink.n_queue_pair:
            options += f"options:n_rxq={uplink.n_queue_pair} " \
                       f"options:n_txq={uplink.n_queue_pair} "
        if uplink.n_rxq_desc:
            options += f"options:n_rxq_desc={uplink.n_rxq_desc} "
        if uplink.n_txq_desc:
            options += f"options:n_txq_desc={uplink.n_txq_desc} "
        self.execute(f"ovs-vsctl add-port {br_name} {uplink.name} " \
            f"-- set Interface {uplink.name} type=dpdk " \
            f"options:dpdk-devargs={uplink.pci_addr} " \
            f"{options} ofport_request={uplink.ofp}")

    def _create_uplink_bond_impl(self, br):
        # Create a pseudo uplink object for bond
        bond_uplink = Uplink(None)
        bond_uplink.name = "bondif"
        bond_uplink.ofp = Constants.OFP_UPLINK_BASE
        phy_ifs = ''
        ifs_set = ''
        ofp_idx = Constants.OFP_UPLINK_BASE
        for uplink in self.uplinks:
            ofp_idx += 1
            uplink.ofp = ofp_idx
            phy_ifs += f" {uplink.name}"
            ifs_set += f" -- set Interface {uplink.name} type=dpdk " \
                       f"options:n_rxq=1 options:n_txq=1 options:dpdk-devargs={uplink.pci_addr} " \
                       f"ofport_request={uplink.ofp}"
            br.uplinks.append(uplink)

        self.execute(f"ovs-vsctl add-bond {br.name} {bond_uplink.name} {phy_ifs} "
                     f"bond_mode=balance-tcp lacp=active other_config:lacp-time=fast "
                     f"{ifs_set}")
        # No need to track pseudo bond uplink in br

    def start_vswitch(self):
        ### Firstly bind uplink interfaces to uio_pci_generic
        self.execute_host("modprobe uio_pci_generic")
        idx = 1
        for uplink in self.uplinks:
            cmds = [f"{self._dpdk_devbind_full_cmd} -u {uplink.pci_addr}",
                    f"{self._dpdk_devbind_full_cmd} -b uio_pci_generic "
                    f"{uplink.pci_addr}"]
            self.execute_host_batch(cmds)
            uplink.name = f"dpdk{idx}"
            idx += 1

        cmds = ["rm -rf /var/run/openvswitch/*",
                "rm -rf /var/log/openvswitch/*",
                f"rm -rf {self._ovs_bin_dir}/conf.db",
                "mkdir -p /var/run/openvswitch",
                "mkdir -p /var/log/openvswitch"]
        self.execute_host_batch(cmds)

        cmds = [f"ovsdb-tool create {self._ovs_bin_dir}/conf.db " \
                    f"{self._ovs_bin_dir}/vswitch.ovsschema",
                f"ovsdb-server --remote=punix:/var/run/openvswitch/db.sock " \
                    f"--pidfile --detach {self._ovs_bin_dir}/conf.db",
                f"ovs-vsctl --no-wait init",
                f"ovs-vsctl --no-wait set Open_vSwitch " \
                    f". other_config:dpdk-init=true",
                f"ovs-vsctl --no-wait set Open_vSwitch " \
                    f". other_config:dpdk-socket-mem={self._aux_params['socket_mem']} " \
                    f"other_config:dpdk-hugepage-dir={self._aux_params['huge_mnt']}",
                f"ovs-vsctl --no-wait set Open_vSwitch " \
                    f". other_config:userspace-tso-enable=" \
                    f"{str(self._aux_params['userspace_tso']).lower()}",
                f"ovs-vsctl --no-wait set Open_vSwitch " \
                    f". other_config:pmd-cpu-mask={self._aux_params['cpu_mask']}",
                f"ovs-vswitchd unix:/var/run/openvswitch/db.sock " \
                    f"--log-file --pidfile --detach"]

        self.execute_host("ps -ef|grep ovs")
        self.execute_batch(cmds, timeout=300)

        (_, stdout, _) = self.execute_host("pgrep ovs-vswitchd")
        dp_pid = int(stdout)
        # Attach background gdb if requested
        if BuiltIn().get_variable_value("${ATTACH_GDB}"):
            self.execute_host("screen -XS gdbscreen quit")
            self.execute_host(f"screen -d -m -S gdbscreen "
                              f"bash -c \"sudo gdb -ex c -p {dp_pid}\"")


class OvsNative(VirtualSwitch):
    """Methods for kernel datapath virtual switch. """
    #def __init__(self, ssh_info, uplinks_spec, tep_addr, ovs_bin_dir, dpdk_devbind_dir):
    #    super().__init__(ssh_info, uplinks_spec, tep_addr, ovs_bin_dir, dpdk_devbind_dir)

    def _create_bridge_impl(self, br):
        self.execute(f"ovs-vsctl add-br {br.name} " \
                f"-- set bridge {br.name} datapath_type=system")

    def _create_vhost_user_interface_impl(self, br_name, vif):
        # Make all 'tap' port  mtu to 9000 to avoid any additional
        # configuration for JUMBO test.
        # Each vhost user interface has its own ifup/ifdown scripts,
        # as we neeed to set ofp while qemu cannot pass those params.
        self.execute_host(
            "sh -c 'cat << EOF > {}\n"
            "#!/bin/sh\n"
            "\n"
            "{}/ovs-vsctl add-port {} $1 "
            "-- set Interface $1 ofport_request={}\n"
            "ip link set $1 up\n"
            "ip link set $1 mtu 9000\n"
            "EOF'"\
            .format(vif.qemu_script_ifup, self._ovs_bin_dir, br_name, vif.ofp))
        self.execute_host(f"chmod u+x {vif.qemu_script_ifup}")

        self.execute_host(
            "sh -c 'cat << EOF > {}\n"
            "#!/bin/sh\n"
            "\n"
            "ip link set $1 down\n"
            "{}/ovs-vsctl del-port {} $1\n"
            "EOF'"\
            .format(vif.qemu_script_ifdown, self._ovs_bin_dir, br_name))
        self.execute_host(f"chmod u+x {vif.qemu_script_ifdown}")

    def _create_uplink_interface_impl(self, br_name, uplink):
        # using 1 rxq/txq pair
        if uplink.n_queue_pair:
            cmd = f"ethtool -L {uplink.name} combined {uplink.n_queue_pair}"
            (ret_code, _, stderr) = self.execute_host(cmd)
            if ret_code != 0:
                logger.warn(f"cmd[{cmd}] failed: {stderr}")

        if uplink.n_rxq_desc:
            cmd = f"ethtool -G {uplink.name} rx {uplink.n_rxq_desc}"
            (ret_code, _, stderr) = self.execute_host(cmd)
            if ret_code != 0:
                logger.warn(f"cmd[{cmd}] failed: {stderr}")

        if uplink.n_txq_desc:
            cmd = f"ethtool -G {uplink.name} tx {uplink.n_txq_desc}"
            (ret_code, _, stderr) = self.execute_host(cmd)
            if ret_code != 0:
                logger.warn(f"cmd[{cmd}] failed: {stderr}")

        self.execute(f"ovs-vsctl add-port {br_name} {uplink.name} "
                     f"-- set Interface {uplink.name} ofport_request={uplink.ofp}")
        self.execute_host(f"ip link set {uplink.name} up")

    def _create_uplink_bond_impl(self, br):
        # Create a pseudo uplink object for bond
        bond_uplink = Uplink(None)
        bond_uplink.name = "bondif"
        bond_uplink.ofp = Constants.OFP_UPLINK_BASE
        phy_ifs = ''
        for uplink in self.uplinks:
            phy_ifs += f" {uplink.name}"

        cmds = [f"modprobe bonding miimon=100 mode=4 lacp_rate=1",
                f"ip link add name {bond_uplink.name} type bond",
                f"ip link set dev {bond_uplink.name} up",
                f"ifenslave {bond_uplink.name} {phy_ifs}",]
        self.execute_host(cmds)

        self.execute(f"ovs-vsctl add-port {br.name} {bond_uplink.name} "
                     f"-- set Interface {bond_uplink.name} ofport_request={bond_uplink.ofp}")
        br.uplinks.append(bond_uplink)

    def _delete_uplink_impl(self, uplink):
        if not uplink.pci_addr:
            self.execute_host(f"ip link del dev {uplink.name}")

    def _set_bond_member_up_impl(self, if_name, up=True):
        if up:
            self.execute_host(f"ip link set dev {if_name} up")
        else:
            self.execute_host(f"ip link set dev {if_name} down")

    def start_vswitch(self):
        cmd = f"{self._dpdk_devbind_full_cmd} --status"
        (_, stdout, _) = self.execute_host(cmd)
        driver_lines = stdout.split("\n")

        for uplink in self.uplinks:
            driver = None
            for line in driver_lines:
                if line.find(uplink.pci_addr) == -1:
                    continue

                if line.find('XL710') != -1:
                    driver = 'i40e'
                elif line.find('X710') != -1:
                    driver = 'i40e'
                elif line.find('82599') != -1:
                    driver = 'ixgbe'
                elif line.find('82540') != -1:
                    driver = 'e1000'

                if driver:
                    break
            if not driver:
                raise RuntimeError(f"no kernel driver found for {uplink.pci_addr}")

            cmds = [f"{self._dpdk_devbind_full_cmd} -u {uplink.pci_addr}",
                    f"{self._dpdk_devbind_full_cmd} -b {driver} {uplink.pci_addr}"]
            self.execute_host_batch(cmds)

        # Refresh driver bind info to get kernel interface name
        cmd = f"{self._dpdk_devbind_full_cmd} --status"
        (_, stdout, _) = self.execute_host(cmd)
        driver_lines = stdout.split("\n")
        regex = re.compile(r"if=(\S+) ")
        for uplink in self.uplinks:
            for line in driver_lines:
                if line.find(uplink.pci_addr) != -1:
                    result = regex.search(line)
                    if result:
                        uplink.name = result.group(1)
                        break
            if not uplink.name:
                raise RuntimeError(f"no kernel interface found for {uplink.pci_addr}")

        cmds = ["rm -rf /var/run/openvswitch/*",
                "rm -rf /var/log/openvswitch/*",
                f"rm -rf {self._ovs_bin_dir}/conf.db",
                "mkdir -p /var/run/openvswitch",
                "mkdir -p /var/log/openvswitch",
                # linux 4.4 kernel bundled ovs datapath cannot load those LKM,
                # automatically, let's load them for interop test
                "modprobe nf_conntrack_ipv4",
                "modprobe nf_conntrack_ipv6",
                "modprobe openvswitch"]
        self.execute_host_batch(cmds)

        cmds = [f"ovsdb-tool create {self._ovs_bin_dir}/conf.db " \
                    f"{self._ovs_bin_dir}/vswitch.ovsschema",
                f"ovsdb-server --remote=punix:/var/run/openvswitch/db.sock " \
                    f"--pidfile --detach {self._ovs_bin_dir}/conf.db",
                f"ovs-vsctl --no-wait init",
                f"ovs-vswitchd unix:/var/run/openvswitch/db.sock " \
                    f"--log-file --pidfile --detach"]

        self.execute_batch(cmds, timeout=100)
