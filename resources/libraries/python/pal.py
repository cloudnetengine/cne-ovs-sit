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

"""Defines keywords for robot tests, PAL stands for Python Adaption Layer."""

from robot.api import logger
from resources.libraries.python.topology import suts

__all__ = [
    u"create_bridge_on_all_suts",
    u"delete_bridge_on_all_suts",
    u"setup_uplink_bridge_on_all_suts",
    u"teardown_uplink_bridge_on_all_suts",
    u"add_vif_ports_on_all_suts",
    u"delete_vif_ports_on_all_suts",
    u"bump_uplink_mtu_on_all_suts",
    u"flush_revalidator_on_all_suts",
    u"flush_conntrack_on_all_suts",
    u"set_port_vlan_on_all_suts",
    u"start_vms_on_all_suts",
    u"stop_vms_on_all_suts",
    u"set_vm_mtu_on_all_suts",
    u"verify_topology_get",
    u"verify_topology_allow_originate",
    u"verify_topology_select_pair",
    u"verify_topology_change_allow_to_deny",
    u"verify_topology_change_deny_to_allow",
    u"execute_ping_verification",
    u"execute_iperf_verification",
    u"execute_performance_test",
    u"VerifyTopology",
    u"VerifyTopologyEntry",
    u"EndPoint",
]

def create_bridge_on_all_suts(br_name):
    """Create bridges on all SUTS.
    :param br_name: Bridge name.
    :type br_name: str
    """
    for sut in suts:
        sut.vswitch.create_bridge(br_name)

def delete_bridge_on_all_suts(br_name):
    """Delete bridges on all SUTS.
    :param br_name: Bridge name.
    :type br_name: str
    """
    for sut in suts:
        sut.vswitch.delete_bridge(br_name)

def setup_uplink_bridge_on_all_suts(br_name, bond=False):
    """Create uplink bridges on all SUTS.
    :param br_name: Bridge name.
    :param bond: Configure uplink bond or not.
    :type br_name: str
    :type bond: bool
    """
    for sut in suts:
        sut.vswitch.create_uplink_bridge(br_name, bond)

def teardown_uplink_bridge_on_all_suts(br_name):
    """Delete uplink bridges on all SUTS.
    :param br_name: Bridge name.
    :type br_name: str
    """
    for sut in suts:
        sut.vswitch.delete_uplink_bridge(br_name)

def bump_uplink_mtu_on_all_suts(mtu):
    """Set uplink MTU on all SUTS.
    :param mtu: Requested MTU.
    :type mtu: int
    """
    for sut in suts:
        sut.vswitch.set_uplink_mtu(mtu)

def flush_revalidator_on_all_suts():
    """Flush vswitch revalidator on all SUTS. """
    for sut in suts:
        sut.vswitch.execute("ovs-appctl revalidator/purge")

def flush_conntrack_on_all_suts():
    """Flush all datapath conntrack states on all duts. """
    for sut in suts:
        sut.vswitch.execute("ovs-appctl dpctl/flush-conntrack")
        sut.vswitch.execute("ovs-appctl dpctl/dump-conntrack -m")

def set_port_vlan_on_all_suts(port_name, vlan_id):
    """Set ports' VLAN on all SUTS.
    :param port_name: Ports' name.
    :param vlan_id: Requested VLAN ID.
    :type port_name: str
    :type vlan_id: int
    """
    for sut in suts:
        sut.vswitch.set_port_vlan(port_name, vlan_id)

def add_vif_ports_on_all_suts(br_name):
    """Attach VM's VIFs to bridges on all SUTS.
    :param br_name: Name of bridges to attach.
    :type br_name: str
    """
    for sut in suts:
        for vm in sut.get_vms():
            for vif in vm.vifs:
                sut.vswitch.create_vhost_user_interface(br_name, vif)

def delete_vif_ports_on_all_suts(br_name):
    """Dettach VM's VIFs from bridges on all SUTS.
    :param br_name: Name of bridges to dettach.
    :type br_name: str
    """
    for sut in suts:
        for vm in sut.get_vms():
            for vif in vm.vifs:
                sut.vswitch.delete_interface(br_name, vif.name)

def start_vms_on_all_suts():
    """Poweron VMs on all SUTS. """
    for sut in suts:
        for vm in sut.get_vms():
            vm.qemu_start()

def stop_vms_on_all_suts():
    """Poweroff VMs on all SUTS. """
    for sut in suts:
        for vm in sut.get_vms():
            vm.qemu_guest_poweroff()

def set_vm_mtu_on_all_suts(mtu):
    """Configure VM's interface MTU on all SUTS.
    :param mtu: Requested MTU.
    :type mtu: int
    """
    for sut in suts:
        for vm in sut.get_vms():
            vm.configure_mtu(mtu)

class Locality:
    """Contains locality definitions."""
    UNDEF = 0
    NUMA = 1
    XNUMA = 2
    XHOST = 3

class EPCriteria:
    """Contains endpoint selection criterias."""
    def __init__(self):
        self.pnic_loc = Locality.UNDEF

class TopologyCriteria:
    """Contains topology criterias for source/dest endpoints
    and their locality relation.
    """
    def __init__(self):
        self.sepc = EPCriteria()
        self.depc = EPCriteria()
        self.locc = Locality.UNDEF

class EndPoint:
    """Contains endpoint definition."""
    def __init__(self, host, guest, vif):
        self.host = host
        self.guest = guest
        self.vif = vif

    def __str__(self):
        return f"host:{self.host.name} guest:{self.guest.name}  vif:{self.vif.name}"

class VerifyTopologyEntry:
    """Contains definition for an entry in a verify topology.
    It contains a source endpoint and matched destination endpoints,
    and destination endpoints are organized by locality relation
    with the source endpoint, i.e. same NUMA, cross NUMA, cross host.
    """
    def __init__(self, sep):
        self.sep = sep
        self.dep_numa = list()
        self.dep_xnuma = list()
        self.dep_xhost = list()

    def get_deps(self):
        """Get destination endpoints.
        Return at most one destination endpoint for each locality relation.
        """
        deps = list()
        if len(self.dep_numa) != 0:
            deps.append(self.dep_numa[0])
        if len(self.dep_xnuma) != 0:
            deps.append(self.dep_xnuma[0])
        if len(self.dep_xhost) != 0:
            deps.append(self.dep_xhost[0])
        return deps

    def get_full_deps(self):
        """Get all matched destination endpoints. """
        deps = list()
        deps += self.dep_numa
        deps += self.dep_xnuma
        deps += self.dep_xhost
        return deps

class VerifyTopology:
    """Defind a topology for verification.
    All entries are classified as either allow or deny.
    """
    def __init__(self):
        self.allow = list()
        self.deny = list()

    def __str__(self):
        s = 'allow:\n'
        for vte in self.allow:
            s += f"\tsep:{vte.sep}\n"
            for dep in vte.dep_numa:
                s += f"\t\tdep_numa:{dep}\n"
            for dep in vte.dep_xnuma:
                s += f"\t\tdep_xnuma:{dep}\n"
            for dep in vte.dep_xhost:
                s += f"\t\tdep_xhost:{dep}\n"
        return s

def _get_vte(vte_list, sep):
    for vte in vte_list:
        if sep == vte.sep:
            return vte

    vte = VerifyTopologyEntry(sep)
    vte_list.append(vte)
    return vte

def verify_topology_get(tc=TopologyCriteria()):
    """Get a typical topology for verification.
    :param tc: Criterias for verification.
    :type tc: TopologyCriteria obj
    """
    vt = VerifyTopology()

    # Select source EndPoint on the first sut
    sep = None
    sut = suts[0]
    for vm in sut.get_vms():
        if ((tc.sepc.pnic_loc == Locality.NUMA
             and vm.numa_id != sut.pnic.numa_id)
                or (tc.sepc.pnic_loc == Locality.XNUMA
                    and vm.numa_id == sut.pnic.numa_id)):
            continue

        # Using the 1st VIF of the VM
        vif = vm.vifs[0]

        sep = EndPoint(sut, vm, vif)
        break

    if sep is None:
        raise RuntimeError("No valid source endpoint is found.")

    # Lookup all the valid destination EndPoint
    for sut in suts:
        if ((tc.locc == Locality.XHOST and sut == sep.host)
                or ((tc.locc == Locality.NUMA or tc.locc == Locality.XNUMA)
                    and sut != sep.host)):
            continue

        for vm in sut.get_vms():
            if ((tc.locc == Locality.NUMA and vm.numa_id != sep.guest.numa_id)
                    or (tc.locc == Locality.XNUMA
                        and vm.numa_id == sep.guest.numa_id)):
                continue

            if ((tc.depc.pnic_loc == Locality.NUMA
                 and vm.numa_id != sut.pnic.numa_id)
                    or (tc.depc.pnic_loc == Locality.XNUMA
                        and vm.numa_id == sut.pnic.numa_id)):
                continue

            for vif in vm.vifs:
                # Skip the source endpoint
                if sut == sep.host and vm == sep.guest and vif == sep.vif:
                    continue

                if not vif.has_same_subnet(sep.vif):
                    continue

                if vif.vni == sep.vif.vni:
                    vte = _get_vte(vt.allow, sep)
                else:
                    vte = _get_vte(vt.deny, sep)


                dep = EndPoint(sut, vm, vif)
                if sep.host != dep.host:
                    vte.dep_xhost.append(dep)
                elif sep.guest.numa_id != dep.guest.numa_id:
                    vte.dep_xnuma.append(dep)
                else:
                    vte.dep_numa.append(dep)

    return vt

def verify_topology_allow_originate(vt):
    """Given an input verify topology, copy an allowed verify entry A
    into a new verify topology's allow list, and construct
    the new verify topology's deny entries by A's dep -> A's sep.
    :param vt: Input verify topology.
    :type vt: VerifyTopology obj
    :returns: source endpoint, new verify topology.
    :rtype: tuple(EndPoint, VerifyTopology)
    """
    new_vt = VerifyTopology()

    if len(vt.allow) == 0:
        raise RuntimeError("No allowed entry is found.")

    # Select the 1st allowed vte as the target
    vte = vt.allow[0]
    new_vt.allow.append(vte)

    for dep in vte.dep_numa:
        # Reverse the 'sep' and 'dep' on deny list
        deny_vte = VerifyTopologyEntry(dep)
        deny_vte.dep_numa.append(vte.sep)
        new_vt.deny.append(deny_vte)
    for dep in vte.dep_xnuma:
        # Reverse the 'sep' and 'dep' on deny list
        deny_vte = VerifyTopologyEntry(dep)
        deny_vte.dep_xnuma.append(vte.sep)
        new_vt.deny.append(deny_vte)
    for dep in vte.dep_xhost:
        # Reverse the 'sep' and 'dep' on deny list
        deny_vte = VerifyTopologyEntry(dep)
        deny_vte.dep_xhost.append(vte.sep)
        new_vt.deny.append(deny_vte)

    return (vte.sep, new_vt)

def verify_topology_select_pair(vt, loc):
    """Given an input verify topology and locality criteria,
    return a new verify topology contains a matched pair.
    :param vt: Input verify topology.
    :param loc: locality criteria.
    :type vt: VerifyTopology obj
    :type loc: str
    :returns: New verify topology.
    :rtype: VerifyTopology obj
    """
    new_vt = VerifyTopology()

    if len(vt.allow) == 0:
        raise RuntimeError("No allowed entry is found.")

    # Select the 1st allowed vte as the target
    vte = vt.allow[0]
    new_vte = VerifyTopologyEntry(vte.sep)

    if loc == 'NUMA':
        if len(vte.dep_numa) == 0:
            raise RuntimeError("No {loc} pair is found.")
        new_vte.dep_numa.append(vte.dep_numa[0])
    elif loc == 'XNUMA':
        if len(vte.dep_xnuma) == 0:
            raise RuntimeError("No {loc} pair is found.")
        new_vte.dep_xnuma.append(vte.dep_xnuma[0])
    elif loc == 'XHOST':
        if len(vte.dep_xhost) == 0:
            raise RuntimeError("No {loc} pair is found.")
        new_vte.dep_xhost.append(vte.dep_xhost[0])
    else:
        raise RuntimeError("{loc} pair is not supported.")

    new_vt.allow.append(new_vte)
    return new_vt

def verify_topology_change_allow_to_deny(vt):
    """Given an input verify topology, moves all allow entries to deny.
    :param vt: Input verify topology.
    :type vt: VerifyTopology obj
    """
    if len(vt.allow) == 0:
        raise RuntimeError("No allowed entry is found.")

    vt.deny = vt.allow
    vt.allow = list()
    logger.debug(f"Verify topology after change allow to deny.\n{vt}")

def verify_topology_change_deny_to_allow(vt):
    """Given an input verify topology, moves all deny entries to allow.
    :param vt: Input verify topology.
    :type vt: VerifyTopology obj
    """
    if len(vt.deny) == 0:
        raise RuntimeError("No denied entry is found.")

    vt.allow = vt.deny
    vt.deny = list()
    logger.debug(f"Verify topology after change allow to deny.\n{vt}")

def execute_ping_verification(vt):
    """Given an input verify topology, execute ping tests.
    :param vt: Input verify topology.
    :type vt: VerifyTopology obj
    """
    for vte in vt.allow:
        svm = vte.sep.guest
        for dep in vte.get_deps():
            svm.ping_ipv4_addr(dep.vif.if_addr.ipv4)
            svm.ping_ipv6_addr(dep.vif.if_addr.ipv6)

    for vte in vt.deny:
        svm = vte.sep.guest
        for dep in vte.get_deps():
            svm.ping_ipv4_addr(dep.vif.if_addr.ipv4, exp_fail=True)
            svm.ping_ipv6_addr(dep.vif.if_addr.ipv6, exp_fail=True)

def execute_iperf_verification(vt, proto='tcp', parallel=1):
    """Given an input verify topology, execute iperf tests.
    :param vt: Input verify topology.
    :type vt: VerifyTopology obj
    :returns: Test results.
    :rtype: str
    """
    results = list()
    for vte in vt.allow:
        svm = vte.sep.guest
        for dep in vte.get_deps():
            result = svm.execute_iperf_ipv4(dep.guest, dep.vif.if_addr.ipv4,
                                            proto=proto, parallel=parallel)
            results.append(result)
            result = svm.execute_iperf_ipv6(dep.guest, dep.vif.if_addr.ipv6,
                                            proto=proto, parallel=parallel)
            results.append(result)

    for vte in vt.deny:
        svm = vte.sep.guest
        for dep in vte.get_deps():
            svm.execute_iperf_ipv4(dep.guest, dep.vif.if_addr.ipv4,
                                   proto=proto, exp_fail=True)
            svm.execute_iperf_ipv6(dep.guest, dep.vif.if_addr.ipv6,
                                   proto=proto, exp_fail=True)

    return results

def execute_performance_test(vt):
    """Given an input verify topology, execute performance tests.
    :param vt: Input verify topology.
    :type vt: VerifyTopology obj
    :returns: Test results.
    :rtype: list(str)
    """
    results = list()
    for vte in vt.allow:
        svm = vte.sep.guest
        for dep in vte.get_deps():
            for proto in ['tcp', 'udp']:
                result = svm.execute_iperf_ipv4(dep.guest, dep.vif.if_addr.ipv4,
                                                proto=proto)
                results.append(result)
                result = svm.execute_iperf_ipv6(dep.guest, dep.vif.if_addr.ipv6,
                                                proto=proto)
                results.append(result)
            result = svm.execute_netperf_ipv4(dep.guest, dep.vif.if_addr.ipv4)
            results.append(result)
            result = svm.execute_netperf_ipv6(dep.guest, dep.vif.if_addr.ipv6)
            results.append(result)

    return results
