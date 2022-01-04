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

"""Defines nodes and topology structure."""

import os
import sys
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from yaml import safe_load

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
from resources.libraries.python.constants import Constants
from resources.libraries.python.vif import VhostUserInterface, InterfaceAddress
from resources.libraries.python.ssh import exec_cmd, kill_process
from resources.libraries.python.vm import VirtualMachine
from resources.libraries.python.vswitch import OvsDpdk, OvsNative

__all__ = [
    u"init_topology",
]

_TMP_DIR = "temp"
# Please make sure tep's IP networks are not conflict against
# SUT's management IP networks.
_TEP_NETV4 = IPv4Network("10.111.0.0/16")
_TEP_NETV6 = IPv6Network('2001:1000:1000:1000:0:0:0a6f:0000/112')

def _atoi(s):
    try:
        return int(s)
    except ValueError:
        return 0

class Node():
    """Define attributes for a managed node. """
    def __init__(self, name, node_spec):
        self.name = name
        self.ssh_info = dict()
        self.ssh_info['host'] = node_spec['host']
        self.ssh_info['port'] = node_spec['port']
        self.ssh_info['username'] = node_spec['username']
        self.ssh_info['password'] = node_spec['password']

class Numa():
    """Define attributes for a NUMA node. """
    def __init__(self, numa_id):
        self.numa_id = numa_id
        self.avail_cpus = list()
        self.avail_mem = 0
        self.vms = list()

class SUT(Node):
    """Define attributes and methods for a SUT (System Under Test) node.
    A SUT node is normally a host which runs virtual switch and guests.
    """
    HUGE_MNT = '/dev/hugepages'
    HUGEPAGE_SIZE = 1024 # MB
    OVSDPDK_MEM_PER_SOCKET = (1024 * 512) # KB
    OVSDPDK_PNIC_NUMA_CPU_NUM = 1
    OVSDPDK_NORM_NUMA_CPU_NUM = 1
    MAX_VM_PER_NUMA = 2

    def __init__(self, name, node_spec):
        super().__init__(name, node_spec)

        self.huge_mnt = node_spec.get('huge_mnt', SUT.HUGE_MNT)
        self.userspace_tso = node_spec.get('userspace_tso', True)
        self.numas = list()
        self.hugepage_size = int(node_spec.get('hugepage_size', SUT.HUGEPAGE_SIZE))
        self.hugepage_size *= 1024 # To KB

        cmd = "lscpu -p"
        _, stdout, _ = exec_cmd(self.ssh_info, cmd)

        # Need to destory stale processes before collecting the available resources.
        kill_process(self.ssh_info, "qemu-system-x86_64")
        kill_process(self.ssh_info, "ovs-vswitchd")
        kill_process(self.ssh_info, "ovsdb-server")
        # Remove stale rtemap entries
        exec_cmd(self.ssh_info, f"rm -rf {self.huge_mnt}/rtemap_*")

        ## CPU,Core,Socket,Node,,L1d,L1i,L2,L3,L4
        #0,0,0,0,,0,0,0,0,0
        #1,1,0,0,,1,1,1,1,1
        self.cpuinfo = list()
        for line in stdout.split("\n"):
            if len(line) > 0 and line[0] != "#":
                self.cpuinfo.append([_atoi(x) for x in line.split(",")])
        # Last line contains the largest numa node id
        self.n_numa = self.cpuinfo[-1][3] + 1
        # Construct NUMA core list mapping
        for numa_id in range(self.n_numa):
            numa = Numa(numa_id)
            cmd = f"cat /sys/devices/system/node/node{numa_id}/" \
                  f"hugepages/hugepages-{self.hugepage_size}kB/free_hugepages"
            ret_code, stdout, stderr = exec_cmd(self.ssh_info, cmd)
            stdout = stdout.strip()
            if ret_code:
                # Current numa node doesn't have any hugepage requested.
                continue
            try:
                free_hugepages = int(stdout)
                if free_hugepages < 0:
                    # In some system without numa enabled, normalized to 0
                    free_hugepages = 0
            except ValueError:
                logger.error(f"Reading numa hugepage failed : {cmd} {stdout}")
                sys.exit()
            numa.avail_mem = self.hugepage_size * free_hugepages
            self.numas.append(numa)

        for cpu in self.cpuinfo:
            self.numas[cpu[3]].avail_cpus.append(cpu[0])
        # Don't use core 0
        self.numas[0].avail_cpus.remove(0)

        self.pnic_numa_id = None
        uplinks_spec = node_spec.get("interfaces", dict())
        for iface in uplinks_spec.keys():
            iface_spec = uplinks_spec[iface]
            cmd = f"cat /sys/bus/pci/devices/{iface_spec['pci_address']}/numa_node"
            _, stdout, _ = exec_cmd(self.ssh_info, cmd)
            try:
                numa_id = int(stdout)
                if numa_id < 0:
                    # In some system without numa enabled, normalized to 0
                    numa_id = 0
            except ValueError:
                logger.error(f"Reading numa location failed for: {iface_spec['pci_address']}")
                sys.exit()
            if not self.pnic_numa_id:
                self.pnic_numa_id = numa_id
            else:
                if numa_id != self.pnic_numa_id:
                    logger.warn(f"uplink interfaces CANNOT be on different numa nodes")
                    sys.exit()

        self.test_root_dir = node_spec.get("test_root_dir")
        if not self.test_root_dir:
            (_, stdout, _) = exec_cmd(self.ssh_info, 'echo ~')
            self.test_root_dir = os.path.join(str(stdout).strip(), "TEST_ROOT/")

        self.test_tmp_dir = os.path.join(self.test_root_dir, _TMP_DIR)
        exec_cmd(self.ssh_info, f"rm -rf {self.test_tmp_dir}")
        exec_cmd(self.ssh_info, f"mkdir -p {self.test_tmp_dir}")

        self.vhost_sock_dir = "/var/run/openvswitch"
        self.vms = list()

        guest_vcpu_idx = 0

        node_idx = int(node_spec['id'])
        dp_type = node_spec.get("dp_type", "ovs-dpdk")
        dpdk_devbind_dir = os.path.join(self.test_root_dir, "bin/")
        ovs_bin_dir = os.path.join(self.test_root_dir, f"bin/{dp_type}/")

        tep_ipv4 = list(_TEP_NETV4.hosts())[node_idx + 1]
        tep_ipv6 = list(_TEP_NETV6.hosts())[node_idx + 1]
        tep_addr = InterfaceAddress(tep_ipv4, _TEP_NETV4,
                                    tep_ipv6, _TEP_NETV6)
        if dp_type == "ovs-dpdk":
            ovs_native = False
            aux_params = dict()
            socket_mem_str = ''
            # 'numas' is sored by id
            for numa in self.numas:
                socket_mem = max(SUT.OVSDPDK_MEM_PER_SOCKET, self.hugepage_size)
                if numa.avail_mem <= socket_mem:
                    logger.warn(f"numa node:{numa.numa_id} mem:{numa.avail_mem} "
                                f"is not enough for ovsdpdk socket_mem:{socket_mem}. "
                                f"skip this numa node.")
                    # Prevent alloacte vm on this numa node
                    numa.avail_mem = 0
                    socket_mem = 0
                else:
                    # If the left mem is not enough for a VM, no side effect
                    numa.avail_mem -= socket_mem
                socket_mem_str += f"{int(socket_mem/1024)},"
            socket_mem_str = socket_mem_str.rstrip(',')

            cpu_mask = 0
            pnic_numa_cpu_num = int(node_spec.get('pnic_numa_cpu_num',
                                                  SUT.OVSDPDK_PNIC_NUMA_CPU_NUM))
            norm_numa_cpu_num = int(node_spec.get('norm_numa_cpu_num',
                                                  SUT.OVSDPDK_NORM_NUMA_CPU_NUM))
            for numa in self.numas:
                if not numa.avail_mem:
                    # Bypass numa nodes which have no socket_mem allocated.
                    continue

                if numa.numa_id == self.pnic_numa_id:
                    if len(numa.avail_cpus) < pnic_numa_cpu_num:
                        logger.warn(f"pnic numa node:{numa.numa_id} "
                                    f"have have no {pnic_numa_cpu_num} cpus")
                        sys.exit()
                    for _ in range(pnic_numa_cpu_num):
                        cpu = numa.avail_cpus.pop(0)
                        cpu_mask |= 1 << cpu
                else:
                    if len(numa.avail_cpus) < norm_numa_cpu_num:
                        logger.warn(f"norm numa node:{numa.numa_id} "
                                    f"have have no {pnic_numa_cpu_num} cpus")
                        sys.exit()
                    for _ in range(norm_numa_cpu_num):
                        cpu = numa.avail_cpus.pop(0)
                        cpu_mask |= 1 << cpu

            aux_params['socket_mem'] = socket_mem_str
            aux_params['huge_mnt'] = self.huge_mnt
            aux_params['cpu_mask'] = hex(cpu_mask)
            aux_params['userspace_tso'] = self.userspace_tso
            aux_params['driver'] = node_spec.get('driver', 'vfio-pci')
            self.vswitch = OvsDpdk(self.ssh_info, node_spec.get("interfaces", dict()),
                                   tep_addr,
                                   ovs_bin_dir, dpdk_devbind_dir,
                                   aux_params)
        elif dp_type == "ovs-native":
            ovs_native = True
            self.vswitch = OvsNative(self.ssh_info, node_spec.get("interfaces", dict()),
                                     tep_addr,
                                     ovs_bin_dir, dpdk_devbind_dir)
        else:
            raise RuntimeError(f"Do not support {dp_type} type datapath")


        self.vswitch.stop_vswitch()
        self.vswitch.start_vswitch()

        host_ssh_info = {
            'host': node_spec['host'],
            'port': node_spec['port'],
            'username': node_spec['username'],
            'password': node_spec['password'],
            }


        vm_mem_size = int(node_spec.get('vm_mem_size', VirtualMachine.VM_MEM_SIZE))
        vm_mem_size *= 1024 # To KB
        vm_cpu_num = int(node_spec.get('vm_cpu_num', VirtualMachine.VM_CPU_NUM))
        vm_mem_size = max(vm_mem_size, self.hugepage_size)
        if_idx_of_host = 1
        guest_idx = 1

        for numa in self.numas:
            if not numa.avail_mem:
                # Bypass numa nodes which have no socket_mem allocated.
                continue

            for _ in range(SUT.MAX_VM_PER_NUMA):
                if numa.avail_mem < vm_mem_size:
                    break
                if len(numa.avail_cpus) < vm_cpu_num:
                    break

                numa.avail_mem -= vm_mem_size
                vm_host_cpus = []
                for _ in range(vm_cpu_num):
                    vm_host_cpus.append(numa.avail_cpus.pop(0))

                vm_name = 'vm_{0:02d}_{1:02d}'.format(node_idx, guest_idx)
                vm = VirtualMachine(vm_name, guest_idx, vm_mem_size, vm_host_cpus, self.huge_mnt,
                                    host_ssh_info, self.test_root_dir,
                                    ovs_native=ovs_native)

                for if_idx_on_vm in range(VirtualMachine.VM_VIFS_NUM):
                    vif_name = 'vhost_{0:02d}{1:03d}'.format(node_idx, if_idx_of_host)
                    ipv4 = IPv4Address('172.{0}.{1}.{2}'.format(
                        168 + if_idx_on_vm, node_idx, guest_idx))
                    ipv4_network = IPv4Network(f"{ipv4}/16", strict=False)
                    ipv6 = IPv6Address('2001:1000:1000:1000:0:0:' \
                            'ac{0:02x}:{1:02x}{2:02x}'.format(
                                168 + if_idx_on_vm, node_idx, guest_idx))
                    ipv6_network = IPv6Network(f"{ipv6}/112", strict=False)
                    if_addr = InterfaceAddress(ipv4, ipv4_network, ipv6, ipv6_network)
                    mac = '00:00:00:{0:02x}:{1:02x}:{2:02x}'.format(node_idx,
                                                                    guest_idx, if_idx_on_vm + 1)
                    vif = VhostUserInterface(name=vif_name,
                                             idx=if_idx_on_vm,
                                             mac=mac,
                                             ofp=f"{Constants.OFP_VHOST_BASE + if_idx_of_host}")
                    cm = str(node_spec.get('vhost_client_mode', True)).lower()
                    if cm == 'false':
                        vif.backend_client_mode = False

                    vif.if_addr = if_addr
                    vif.sock = os.path.join(self.vhost_sock_dir, vif_name)
                    if dp_type == "ovs-native":
                        path = os.path.join(self.test_tmp_dir, f"{vm_name}_{vif_name}")
                        vif.qemu_script_ifup = f"{path}_ifup"
                        vif.qemu_script_ifdown = f"{path}_ifdown"

                    vm.add_vhost_user_if(vif)
                    if_idx_of_host += 1

                numa.vms.append(vm)
                guest_idx += 1

    def get_vms(self):
        """Get all the virtual machines on the SUT.
        :returns: virtual machines.
        :rtype: list(VirtualMachine obj)
        """
        vms = list()
        for numa in self.numas:
            vms += numa.vms
        return vms

def load_topo_from_yaml():
    """Load topology from file defined in "${TOPOLOGY_PATH}" variable.
    Then constructs all the components defined in the config file.
    """
    try:
        topo_path = BuiltIn().get_variable_value(u"${TOPOLOGY_PATH}")
    except Exception:
        raise "Cannot load topology file."

    nodes_spec = None
    with open(topo_path) as work_file:
        nodes_spec = safe_load(work_file.read())[u"nodes"]

    for name, node_spec in nodes_spec.items():
        if node_spec['type'] == 'SUT':
            sut = SUT(name, node_spec)
            suts.append(sut)

# pylint:disable=global-variable-undefined
def init_topology():
    """Initialize topology. Only be called once for the whole test. """
    global suts
    suts = list()
    load_topo_from_yaml()
