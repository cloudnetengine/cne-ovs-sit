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

"""Defines methods for NAT test."""

import ipaddress
from time import sleep
from io import StringIO
from ipaddress import IPv4Network, IPv6Network

from robot.api import logger
from resources.libraries.python.constants import Constants
from resources.libraries.python.vif import InterfaceAddress
from resources.libraries.python.pal import flush_revalidator_on_all_suts, \
                                           flush_conntrack_on_all_suts
from resources.libraries.python.flowutils import provision_flows, setup_default_pipeline_on_all_duts

__all__ = [
    u"snat_configure_vms",
    u"dnat_configure_vms",
    u"nat_restore_vms",
    u"verify_snat",
    u"verify_snat_related",
    u"verify_dnat",
    u"verify_dnat_related",
]

# NAT router's cif is connected to client network, and sif to server network.
# cif/sif ip address is the first ip address on client and server network respectively.
_NAT_CLIENT_NETV4 = IPv4Network('172.10.0.0/16')
_NAT_CLIENT_NETV6 = IPv6Network('2001:1000:1000:1000:0:0:ac0a::/112')
_NAT_SERVER_NETV4 = IPv4Network('192.200.0.0/16')
_NAT_SERVER_NETV6 = IPv6Network('2001:1000:1000:1000:0:0:c0c8::/112')

# Allocated for virtual address during SNAT
_NAT_SNAT_ADDR_IDX_START = 10
# Number of SNAT ia addresses
_NAT_SNAT_ADDR_NUM = 10
# Allocated for endpoints
_NAT_ENDPOINT_ADDR_IDX_START = 100

_NAT_SNAT_PORT_START = 10001
_NAT_ROUTER_CIF_MAC = '80:88:88:88:88:88'
_NAT_ROUTER_CIF_IPV4 = _NAT_CLIENT_NETV4[1]
_NAT_ROUTER_CIF_IPV6 = _NAT_CLIENT_NETV6[1]
_NAT_ROUTER_SIF_MAC = '60:66:66:66:66:66'
_NAT_ROUTER_SIF_IPV4 = _NAT_SERVER_NETV4[1]
_NAT_ROUTER_SIF_IPV6 = _NAT_SERVER_NETV6[1]

# NAT testing priniciples:
# - two networks: client net/server net
#                 client net is 172.170.0.0/16
#                 server net is 172.168.0.0/16
# - no arp/nd, all neighs are pre configured on each vm
# - DNAT vip is using router cif ip address
# - all non NPAT are using iperf tcp/udp utilities
# - all NPAT are using telnet utility

# vipv4/6 == None meaning snat, otherwise dnat
# port_num == 0 maaning NAT, otherwise NPAT

def _configure_vm(vm, vif, ipv4_routes, ipv6_routes,
                  ipv4_neighs, ipv6_neighs):

    dev = f"virtio{vif.idx}"
    ipv4_str = vif.if_addr.ipv4_str_with_prefix()
    ipv6_str = vif.if_addr.ipv6_str_with_prefix()

    cmds = [f"ip -4 addr flush dev {dev} scope global",
            f"ip -6 addr flush dev {dev} scope global",
            f"ip link set {dev} up",
            f"ip -4 route flush {vif.if_addr.ipv4_network}",
            f"ip -6 route flush {vif.if_addr.ipv6_network}",
            f"ip -4 route flush cache",
            f"ip -6 route flush cache",
            f"ip -4 neigh flush dev {dev}",
            f"ip -6 neigh flush dev {dev}",
            f"ip -4 addr add {ipv4_str} dev {dev}",
            f"ip -6 addr add {ipv6_str} dev {dev}",
            f"ip -4 route flush {vif.if_addr.ipv4_network}",
            f"ip -6 route flush {vif.if_addr.ipv6_network}",
            f"ip -4 route add {vif.if_addr.ipv4_network} dev {dev}",
            f"ip -6 route add {vif.if_addr.ipv6_network} dev {dev}"]

    for route in ipv4_routes:
        cmds.append(f"ip route add {route['net']} via {route['gw']}")

    for route in ipv6_routes:
        cmds.append(f"ip -6 route add {route['net']} via {route['gw']}")

    # permanent neigh entry cannot be flushed, so don't use _no_error
    for neigh in ipv4_neighs:
        cmds.append(f"ip neigh add {neigh['ip']} lladdr {neigh['mac']}"
                    f" dev {dev}")

    for neigh in ipv6_neighs:
        cmds.append(f"ip -6 neigh add {neigh['ip']} lladdr {neigh['mac']}"
                    f" dev {dev}")
    vm.execute_batch(cmds)

def _nat_configure_vms(vt, svr_neigh_ipv4s, svr_neigh_ipv6s):
    """ When this method is returned, 'vt' will be trimmed to keep
    only one VerifyTopologyEntry in allow list. """
    if len(vt.allow) < 1:
        raise "Verify topology doesn't have allowed entry."

    del vt.allow[1:]
    del vt.deny[0:]

    vte = vt.allow[0]
    sep = vte.sep

    ipv4_neighs, ipv6_neighs, ipv4_routes, ipv6_routes = (list() for i in range(4))
    # Config source endpoint firstly
    ipv4_neighs.append({'ip': _NAT_ROUTER_CIF_IPV4, 'mac':_NAT_ROUTER_CIF_MAC})
    ipv6_neighs.append({'ip': _NAT_ROUTER_CIF_IPV6, 'mac':_NAT_ROUTER_CIF_MAC})
    ipv4_routes.append({'net':_NAT_SERVER_NETV4, 'gw':_NAT_ROUTER_CIF_IPV4})
    ipv6_routes.append({'net':_NAT_SERVER_NETV6, 'gw':_NAT_ROUTER_CIF_IPV6})

    # Update sep's vif network addresses
    sep.vif.restore_if_addr = sep.vif.if_addr
    sep.vif.if_addr = InterfaceAddress(
        _NAT_CLIENT_NETV4[_NAT_ENDPOINT_ADDR_IDX_START],
        _NAT_CLIENT_NETV4,
        _NAT_CLIENT_NETV6[_NAT_ENDPOINT_ADDR_IDX_START],
        _NAT_CLIENT_NETV6)
    _configure_vm(sep.guest, sep.vif,
                  ipv4_routes, ipv6_routes,
                  ipv4_neighs, ipv6_neighs)

    # Destination endpoints share the same set of neighs
    ipv4_neighs, ipv6_neighs, ipv4_routes, ipv6_routes = (list() for i in range(4))
    ipv4_neighs.append({'ip': _NAT_ROUTER_SIF_IPV4, 'mac':_NAT_ROUTER_SIF_MAC})
    ipv6_neighs.append({'ip': _NAT_ROUTER_SIF_IPV6, 'mac':_NAT_ROUTER_SIF_MAC})
    # Mapping all server neigh addr to sif mac
    for ipv4 in svr_neigh_ipv4s:
        ipv4_neighs.append({'ip': ipv4, 'mac':_NAT_ROUTER_SIF_MAC})
    for ipv6 in svr_neigh_ipv6s:
        ipv6_neighs.append({'ip': ipv6, 'mac':_NAT_ROUTER_SIF_MAC})

    ipv4_routes.append({'net':_NAT_CLIENT_NETV4, 'gw':_NAT_ROUTER_SIF_IPV4})
    ipv6_routes.append({'net':_NAT_CLIENT_NETV6, 'gw':_NAT_ROUTER_SIF_IPV6})

    idx = 0
    for dep in vte.get_full_deps():
        dep.vif.restore_if_addr = dep.vif.if_addr
        dep.vif.if_addr = InterfaceAddress(
            _NAT_SERVER_NETV4[_NAT_ENDPOINT_ADDR_IDX_START + idx],
            _NAT_SERVER_NETV4,
            _NAT_SERVER_NETV6[_NAT_ENDPOINT_ADDR_IDX_START + idx],
            _NAT_SERVER_NETV6)
        _configure_vm(dep.guest, dep.vif,
                      ipv4_routes, ipv6_routes,
                      ipv4_neighs, ipv6_neighs)
        idx += 1

def nat_restore_vms(vt):
    """Given a verify topology, trim it to retain only one allowed entry,
    then configure relevant VM's network with NAT network configuration.
    Note in NAT test, the 'NAT router' doesn't have ARP/ND implementation,
    so neigh info are pre-configured before any traffic in _configure_vm().

    :param vt: Verify topology.
    :rtype: VerifyTopology obj
    """
    vte = vt.allow[0]
    sep = vte.sep
    sep.vif.if_addr = sep.vif.restore_if_addr
    sep.vif.restore_if_addr = None
    for dep in vte.get_full_deps():
        dep.vif.if_addr = dep.vif.restore_if_addr
        dep.vif.restore_if_addr = None

def snat_configure_vms(vt):
    """Given a verify topology, trim it to retain only one allowed entry,
    then configure relevant VM's network with NAT network configuration.
    Note in NAT test, the 'NAT router' doesn't have ARP/ND implementation,
    so neigh info are pre-configured before any traffic in _configure_vm().

    :param vt: Verify topology.
    :rtype: VerifyTopology obj
    """
    svr_neigh_ipv4s, svr_neigh_ipv6s = (list() for i in range(2))
    for idx in range(_NAT_SNAT_ADDR_NUM):
        svr_neigh_ipv4s.append(_NAT_SERVER_NETV4[_NAT_SNAT_ADDR_IDX_START + idx])
        svr_neigh_ipv6s.append(_NAT_SERVER_NETV6[_NAT_SNAT_ADDR_IDX_START + idx])

    _nat_configure_vms(vt, svr_neigh_ipv4s, svr_neigh_ipv6s)

def dnat_configure_vms(vt):
    """Given a verify topology, trim it to retain only one allowed entry,
    then configure relevant VM's network with NAT network configuration.
    Note in NAT test, the 'NAT router' doesn't have ARP/ND implementation,
    so neigh info are pre-configured before any traffic in _configure_vm().

    :param vt: Verify topology.
    :type: VerifyTopology obj
    """
    svr_neigh_ipv4s, svr_neigh_ipv6s = (list() for i in range(2))
    _nat_configure_vms(vt, svr_neigh_ipv4s, svr_neigh_ipv6s)

class NATSpec:
    """ NAT specification. """
    def __init__(self, ipv4_start, ipv6_start, ia_num,
                 port_start, port_num=0, flags=None, vipv4=None, vipv6=None):
        self.ipv4_ia_start = ipaddress.ip_address(u'{0}'.format(ipv4_start))
        self.ipv6_ia_start = ipaddress.ip_address(u'{0}'.format(ipv6_start))
        self.ia_num = ia_num
        self.port_start = port_start
        self.port_num = port_num
        self.flags = flags
        self.vipv4 = vipv4
        self.vipv6 = vipv6

    def is_snat(self):
        """ Return whether the spec is SNAT. """
        return not self.vipv4

    def is_dnat(self):
        """ Return whether the spec is SNAT. """
        return not self.is_snat()

    def generate_nat_action(self, ipv4=True):
        """ Generate NAT action string.
        :param ipv4: Indicate IPv4 or not.
        :type ipv4: bool
        :returns: NAT action string.
        :rtype: str
        """
        ipv6_need_bracket = False
        # need to bracket ipv6 address when port is given
        if self.port_num:
            ipv6_need_bracket = True

        action = ''
        if self.is_snat():
            action = 'src='
        else:
            action = 'dst='

        if ipv4:
            action += format(self.ipv4_ia_start)
            if self.ia_num > 1:
                action += '-{0}'.format(
                    str(self.ipv4_ia_start + self.ia_num - 1))
        else:
            if ipv6_need_bracket:
                action += '['
            action += format(self.ipv6_ia_start)
            if self.ia_num > 1:
                action += '-{0}'.format(
                    str(self.ipv6_ia_start + self.ia_num - 1))
            if ipv6_need_bracket:
                action += ']'

        if self.port_num:
            action += ':{0}'.format(self.port_start)
            if self.port_num > 1:
                action += '-{0}'.format(
                    self.port_start + self.port_num - 1)

        if self.flags:
            action += ',{0}'.format(self.flags)

        return action

def _parse_kv(s):
    kvs = dict()
    cursor = 0
    cursor_next = s.find('=', cursor)
    while cursor_next != -1:
        key = s[cursor:cursor_next]
        # cursor moves to next position right after '='
        cursor = cursor_next + 1
        if s[cursor] == '(':
            # found start of nest
            cursor += 1
            (inner_kvs, advanced) = _parse_kv(s[cursor:])
            kvs['{0}'.format(key)] = inner_kvs
            cursor += advanced # callee alreay pass ')'
            if s[cursor-1] != ')':
                print("nest termination error")
        else:
            cursor_next = cursor
            # iterate char one by one to find termination of 'value'
            c = ''
            for c in s[cursor:]:
                cursor_next += 1
                if c in (')', ','):
                    break
            # either delimiters or end of string
            kvs['{0}'.format(key)] = s[cursor:cursor_next-1]
            cursor = cursor_next

            if c == ')':
                # meaning we must terminate the current inner process
                # note the cursor is already beyond ')' by one
                break

        # end of processing
        if cursor >= len(s):
            break

        # skip possible ',' right after a nest
        if s[cursor] == ',':
            cursor += 1

        cursor_next = s.find('=', cursor)

    return (kvs, cursor)

def _parse_conns(conntrack_dump):
    conns = list()
    buf = StringIO(conntrack_dump)
    for line in buf.readlines():
        cursor = line.find(',', 0)
        # heading 'proto' is not in k-v format, so special handling
        proto = line[0:cursor]

        (conn, _) = _parse_kv(line[cursor+1:])
        conn['proto'] = proto

        conns.append(conn)

    buf.close()
    return conns

# NOTE: might check other addr/port result in the future
def _check_nat_result(sut, exp_conn_num, proto='tcp'):
    # Always sleep few seconds as real traffic load is kicking in vm's background,
    # and it's easy to skrew in virtualbox setup.
    sleep(3)
    (ret_code, stdout, stderr) = \
        sut.vswitch.execute('ovs-appctl dpctl/dump-conntrack -m')
    conns = _parse_conns(stdout)
    logger.debug('proto:{0} exp_conn_num:{1} \n {2}'.format(
        proto, exp_conn_num, conns))
    live_conn = 0
    for conn in conns:
        if not proto or conn['proto'] == proto:
            live_conn += 1
    if live_conn != exp_conn_num:
        raise RuntimeError("NAT conn num is {0}".format(live_conn))

def _nat_setup_flows(vt, br_name, nat_spec):
    # For all nat testing, flows are setup on client node only
    vte = vt.allow[0]
    sep = vte.sep
    sut = sep.host
    vif = sep.vif

    setup_default_pipeline_on_all_duts(br_name)

    sut.vswitch.execute(f"ovs-ofctl del-flows {br_name} table={Constants.OF_TABLE_NAT}")
    flows = list()

    #### Table 0: connection track all ipv4/v6 traffic
    flows.append(f"table={Constants.OF_TABLE_NAT},"
                 f"priority=10,ip,action=ct\\(nat,table={Constants.OF_TABLE_NAT+1}\\)")
    flows.append(f"table={Constants.OF_TABLE_NAT},"
                 f"priority=10,ipv6,action=ct\\(nat,table={Constants.OF_TABLE_NAT+1}\\)")
    flows.append(f"table={Constants.OF_TABLE_NAT},priority=0,action=drop")

    #### Table 1: Allow new FTP/TFTP control connections
    # Part 1.0: flows for client port as in port
    ipv4_nat_action = nat_spec.generate_nat_action(ipv4=True)
    ipv6_nat_action = nat_spec.generate_nat_action(ipv4=False)

    base = f"table={Constants.OF_TABLE_NAT+1},priority=10,in_port={vif.ofp},ct_state=+new,"
    base_v4 = base
    base_v6 = base
    if nat_spec.is_dnat():
        base_v4 += f"ip,nw_dst={nat_spec.vipv4},"
        base_v6 += f"ipv6,ipv6_dst={nat_spec.vipv6},"
    else:
        base_v4 += 'ip,'
        base_v6 += 'ipv6,'

    # Specific to algs ftp and tftp
    flows.append(f"{base_v4}tcp,tp_dst=21,action="
                 f"ct\\(alg=ftp,commit,nat\\({ipv4_nat_action}\\),"
                 f"table={Constants.OF_TABLE_NAT+2}\\)")
    flows.append(f"{base_v4}udp,tp_dst=69,action="
                 f"ct\\(alg=tftp,commit,nat\\({ipv4_nat_action}\\),"
                 f"table={Constants.OF_TABLE_NAT+2}\\)")
    flows.append(f"{base_v6}tcp6,tp_dst=21,action="
                 f"ct\\(alg=ftp,commit,nat\\({ipv6_nat_action}\\),"
                 f"table={Constants.OF_TABLE_NAT+2}\\)")
    flows.append(f"{base_v6}udp6,tp_dst=69,action="
                 f"ct\\(alg=tftp,commit,nat\\({ipv6_nat_action}\\),"
                 f"table={Constants.OF_TABLE_NAT+2}\\)")
    # Generic to other tcp/tcp6/udp/udp6 and icmp/icmp6 traffic
    flows.append(f"{base_v4}tcp,action="
                 f"ct\\(commit,nat\\({ipv4_nat_action}\\),table={Constants.OF_TABLE_NAT+2}\\)")
    flows.append(f"{base_v4}udp,action="
                 f"ct\\(commit,nat\\({ipv4_nat_action}\\),table={Constants.OF_TABLE_NAT+2}\\)")
    flows.append(f"{base_v4}icmp,action="
                 f"ct\\(commit,nat\\({ipv4_nat_action}\\),table={Constants.OF_TABLE_NAT+2}\\)")
    flows.append(f"{base_v6}tcp6,action="
                 f"ct\\(commit,nat\\({ipv6_nat_action}\\),table={Constants.OF_TABLE_NAT+2}\\)")
    flows.append(f"{base_v6}udp6,action="
                 f"ct\\(commit,nat\\({ipv6_nat_action}\\),table={Constants.OF_TABLE_NAT+2}\\)")
    flows.append(f"{base_v6}icmp6,action="
                 f"ct\\(commit,nat\\({ipv6_nat_action}\\),table={Constants.OF_TABLE_NAT+2}\\)")

    # Part 1.1: related flows for data connection
    flows.append(f"table={Constants.OF_TABLE_NAT+1},priority=10,ct_state=+new+rel,tcp,"
                 f"action=ct\\(table={Constants.OF_TABLE_NAT+2},commit,nat\\)")
    flows.append(f"table={Constants.OF_TABLE_NAT+1},priority=10,ct_state=+new+rel,tcp6,"
                 f"action=ct\\(table={Constants.OF_TABLE_NAT+2},commit,nat\\)")
    flows.append(f"table={Constants.OF_TABLE_NAT+1},priority=10,ct_state=+new+rel,udp,"
                 f"action=ct\\(table={Constants.OF_TABLE_NAT+2},commit,nat\\)")
    flows.append(f"table={Constants.OF_TABLE_NAT+1},priority=10,ct_state=+new+rel,udp6,"
                 f"action=ct\\(table={Constants.OF_TABLE_NAT+2},commit,nat\\)")

    # Part 1.2: established flows
    flows.append(f"table={Constants.OF_TABLE_NAT+1},priority=10,ct_state=+est,"
                 f"action=resubmit\\(,{Constants.OF_TABLE_NAT+2}\\)")

    # Part 1.3: pass related pkts
    flows.append(f"table={Constants.OF_TABLE_NAT+1},priority=10,ct_state=+rel,"
                 f"action=resubmit\\(,{Constants.OF_TABLE_NAT+2}\\)")

    #### Table 2: Jump to l2 matching table after NAT MAC translation
    flows.append(f"table={Constants.OF_TABLE_NAT+2},"
                 f"action=resubmit\\(,{Constants.OF_TABLE_NAT+3}\\),"
                 f"goto_table:{Constants.OF_TABLE_L2_MATCH}")

    #### Table 3: MAC address replacement
    # For traffic to client vm
    flows.append(f"table={Constants.OF_TABLE_NAT+3},ip,nw_dst={vif.if_addr.ipv4},"
                 f"action=mod_dl_dst\\({vif.mac}\\),"
                 f"mod_dl_src\\({_NAT_ROUTER_CIF_MAC}\\)")
    flows.append(f"table={Constants.OF_TABLE_NAT+3},ip6,ipv6_dst={vif.if_addr.ipv6},"
                 f"action=mod_dl_dst\\({vif.mac}\\),"
                 f"mod_dl_src\\({_NAT_ROUTER_CIF_MAC}\\)")

    # For traffic to server vms
    # Must match on l3 addr, as ofp is invalid across hosts.
    for dep in vte.get_full_deps():
        flows.append(f"table={Constants.OF_TABLE_NAT+3},ip,nw_dst={dep.vif.if_addr.ipv4},"
                     f"action=mod_dl_dst\\({dep.vif.mac}\\),"
                     f"mod_dl_src\\({_NAT_ROUTER_SIF_MAC}\\)")
        flows.append(f"table={Constants.OF_TABLE_NAT+3},ip6,ipv6_dst={dep.vif.if_addr.ipv6},"
                     f"action=mod_dl_dst\\({dep.vif.mac}\\),"
                     f"mod_dl_src\\({_NAT_ROUTER_SIF_MAC}\\)")

    provision_flows(sut, br_name, flows)

# NOTE: for RELATED test, we only test on either client or server vm,
# RELATED pkt generated by intermediate device is going to have more
# complicated topology, and we may do that in the future.
#
# direction:
# - 'reply' means generate icmp from server -> client
# - 'orig' means generate icmp from client -> server
def _nat_execute_related(nat_spec, sep, dep, ip_ver, direction):
    client_vm = sep.guest
    server_vm = dep.guest
    if ip_ver == 'ipv4':
        client_ip = sep.vif.if_addr.ipv4
        server_ip = dep.vif.if_addr.ipv4
        if nat_spec.is_snat():
            client_view_server_ip = server_ip
            server_view_client_ip = nat_spec.ipv4_ia_start
        else:
            client_view_server_ip = nat_spec.vipv4
            server_view_client_ip = client_ip

        nc_option = ''
        iptables_option = ''
        iptables_reject_type = 'icmp-host-prohibited'
        related_expected_key = 'unreachable - admin prohibited'
        tcpdump_option = 'icmp'
    else:
        client_ip = sep.vif.if_addr.ipv6
        server_ip = dep.vif.if_addr.ipv6
        if nat_spec.is_snat():
            client_view_server_ip = server_ip
            server_view_client_ip = nat_spec.ipv6_ia_start
        else:
            client_view_server_ip = nat_spec.vipv6
            server_view_client_ip = client_ip

        nc_option = ' -6 '
        iptables_option = '6'
        iptables_reject_type = 'icmp6-adm-prohibited'
        related_expected_key = 'unreachable prohibited'
        tcpdump_option = 'icmp6'

    cmd = "sudo sh -c 'cat << EOF > ./loop\n" \
            "#!/bin/sh\n" \
            "\n" \
            "while true; do \n" \
            "    echo \"hello\"\n" \
            "    sleep 1\n" \
            "done\n'"
    client_vm.execute(cmd)
    server_vm.execute(cmd)
    client_vm.execute("chmod +x ./loop")
    server_vm.execute("chmod +x ./loop")

    # nc server and client each generate pkts by 'loop' input
    # so we can setup iptables reject rule in either nc server or client
    # to trigger either 'reply' or 'orig' direction icmp related msg.
    cmd = 'nohup sh -c \"./loop | nc {0} -u -l -p 10000" >/dev/null 2>&1 &'\
            .format(nc_option)
    server_vm.execute(cmd)

    cmd = "nohup sh -c \"./loop | nc {0} -u {1} 10000\" >/dev/null 2>&1 &" \
            .format(nc_option, client_view_server_ip)
    client_vm.execute(cmd)

    if direction == 'orig':
        tcpdump_vm = server_vm
        tcpdump_if = f"virtio{dep.vif.idx}"
        iptables_vm = client_vm
        iptables_if = f"virtio{sep.vif.idx}"
        reject_ip = client_ip
    else:
        tcpdump_vm = client_vm
        tcpdump_if = f"virtio{sep.vif.idx}"
        iptables_vm = server_vm
        iptables_if = f"virtio{dep.vif.idx}"
        reject_ip = server_ip

    tcpdump_vm.execute('rm -rf ./cap')
    # '-U' option MUST be used, otherwise empty capture file
    cmd = 'nohup tcpdump -U -i {0} {1} -w ./cap >/dev/null 2>&1 &' \
            .format(tcpdump_if, tcpdump_option)
    tcpdump_vm.execute(cmd)

    sleep(3)

    # icmp-host-prohibited is used instead of icmp-port-unreachable
    # because there might be some noises when nc client is quit,
    # ip stack of the nc client vm will also generate port unreachable
    # icmp to nc server (as nc server is keeping sending data).
    cmd = 'ip{0}tables -I INPUT -i {1} -d {2} -j REJECT ' \
          ' --reject-with {3}'.format(
              iptables_option, iptables_if, reject_ip, iptables_reject_type)
    iptables_vm.execute(cmd)

    # nc client actually already quit by recieving the port unreachable icmp,
    # after nc client quit, nc server will also get port unreachable icmp,
    # but it's not quit yet.

    # wait few seconds so the above 'reject' will be triggered
    # thus captured by tcpdump
    sleep(3)

    (_, tcpdump_log, _) = tcpdump_vm.execute('tcpdump -r ./cap')

    # cleanup everything
    cmd = 'ip{0}tables -D INPUT -i {1} -d {2} -j REJECT ' \
          ' --reject-with {3}'.format(
              iptables_option, iptables_if, reject_ip, iptables_reject_type)
    iptables_vm.execute(cmd)

    tcpdump_vm.kill_process("tcpdump")

    # nc client is quit, try to kill it again anyway
    server_vm.kill_process("nc")
    client_vm.kill_process("nc")

    # 09:31:41.874866 IP 172.168.1.2 > 172.170.100.1: ICMP host 172.168.1.2 \
    #        unreachable - admin prohibited, length 42
    # 13:59:34.450321 IP6 2001:1000:1000:1000::aca8:102 > 2001:1000:1000:1000::acaa:6401: \
    #        ICMP6, destination unreachable, unreachable prohibited 2001:1000:1000:1000::aca8:102, \
    #        length 62
    verify_strs = list()
    verify_strs.append(related_expected_key)
    # MUST use ip_address to normalize ipv4/6 address to compare with tcpdump
    if direction == 'orig':
        verify_strs.append(f"{server_view_client_ip} > {server_ip}")
    else:
        verify_strs.append(f"{client_view_server_ip} > {client_ip}")

    for s in verify_strs:
        logger.debug('related key: {0}'.format(s))

    buf = StringIO(tcpdump_log)
    related = 0
    for line in buf.readlines():
        logger.debug('related test line :{0}'.format(line))
        found = True
        for s in verify_strs:
            if not s in line:
                found = False
                break

        if found:
            related += 1

    buf.close()

    if direction == 'reply' and related != 1:
        logger.error('related reply num: {0} is not 1'.format(related))

    # as nc server continous send data, nc client vm iptables
    # will continously send back icmp related msg, thus equal
    # or larger than 1.
    if direction == 'orig' and related == 0:
        logger.error('related orig num cannot be zero')

def verify_snat(vt, ip_num=1, port_num=0, svr_num=1,
                tool='telnet', parallel=1, ping_size=1000):
    """ Given a verify topology, execute SNAT test. """

    if len(vt.allow) != 1:
        raise "Verify topology is invalid."

    ip_num = int(ip_num)
    port_num = int(port_num)
    svr_num = int(svr_num)
    parallel = int(parallel)
    ping_size = int(ping_size)

    #if svr_num > len(cs_verify_spec['ipv4_servers']):
    #    logger.error('svr_num:{0} is larger than available:{1}'.format(
    #        svr_num, len(cs_verify_spec['ipv4_servers'])))
    #    return
    #if tool == 'iperf_tcp' or tool == 'iperf_udp':
    #    if svr_num > 1:
    #        logger.error('iperf test iterate all available servers')
    #        return

    # don't support testing to parallel tftp/ftp
    if tool in ('tftp', 'ftp_passive', 'ftp_active'):
        if parallel > 1:
            logger.error('file copy test cannot support parallel')
            return

    # flush all conntrack state firstly
    flush_conntrack_on_all_suts()
    flush_revalidator_on_all_suts()

    nat_spec = NATSpec(_NAT_SERVER_NETV4[_NAT_SNAT_ADDR_IDX_START],
                       _NAT_SERVER_NETV6[_NAT_SNAT_ADDR_IDX_START],
                       ip_num,
                       _NAT_SNAT_PORT_START, port_num)

    _nat_setup_flows(vt, 'br0', nat_spec)

    vte = vt.allow[0]
    sep = vte.sep

    if tool == 'telnet':
        for s in range(svr_num):
            for _ in range(parallel):
                dep = vte.get_full_deps()[s]
                cmd = f"telnet {dep.vif.if_addr.ipv4} 22 &"
                sep.guest.execute(cmd)
                cmd = f"telnet {dep.vif.if_addr.ipv6} 22 &"
                sep.guest.execute(cmd)

        _check_nat_result(sep.host, parallel*svr_num*2, 'tcp')
        sep.guest.kill_process("telnet")
    elif tool == 'ping':
        for s in range(svr_num):
            for _ in range(parallel):
                dep = vte.get_full_deps()[s]
                cmd = f"ping -c 3 -i 0.3 -s {ping_size} {dep.vif.if_addr.ipv4} &"
                sep.guest.execute(cmd)
                cmd = f"ping -6 -c 3 -i 0.3 -s {ping_size} {dep.vif.if_addr.ipv6} &"
                sep.guest.execute(cmd)

        _check_nat_result(sep.host, parallel*svr_num*2, None)
        sep.guest.kill_process("ping")
    #elif tool == 'iperf_tcp':
    #    for server in cs_verify_spec['ipv4_servers']:
    #        ss = "${{{0}}}".format(server['vm'])
    #        vm = BuiltIn().get_variable_value(ss)
    #        cne_execute_iperf_ipv4(client_vm,
    #            vm, server['ipv4'], 0, 'tcp', parallel)

    #        # hopefully all conntracks are still in FIN state
    #        _check_nat_result(node, parallel + 1, 'tcp')

    #    for server in cs_verify_spec['ipv6_servers']:
    #        ss = "${{{0}}}".format(server['vm'])
    #        vm = BuiltIn().get_variable_value(ss)
    #        cne_execute_iperf_ipv6(client_vm,
    #            vm, server['ipv6'], 0, 'tcp', parallel)

    #        # hopefully all conntracks are still in FIN state
    #        _check_nat_result(node, parallel + 1, 'tcp')

    #elif tool == 'iperf_udp':
    #    for server in cs_verify_spec['ipv4_servers']:
    #        ss = "${{{0}}}".format(server['vm'])
    #        vm = BuiltIn().get_variable_value(ss)
    #        cne_execute_iperf_ipv4(client_vm,
    #            vm, server['ipv4'], 0, 'udp', parallel)

    #        # hopefully all conntracks are still in FIN state
    #        _check_nat_result(node, parallel + 1, None)

    #    for server in cs_verify_spec['ipv6_servers']:
    #        ss = "${{{0}}}".format(server['vm'])
    #        vm = BuiltIn().get_variable_value(ss)
    #        cne_execute_iperf_ipv6(client_vm,
    #            vm, server['ipv6'], 0, 'udp', parallel)

    #        # hopefully all conntracks are still in FIN state
    #        _check_nat_result(node, parallel + 1, None)

    elif tool == 'tftp':
        for s in range(svr_num):
            dep = vte.get_full_deps()[s]
            sep.guest.execute_tftp(dep.guest, dep.vif.if_addr.ipv4)
            sep.guest.execute_tftp(dep.guest, dep.vif.if_addr.ipv6)

    elif tool == 'ftp_active':
        for s in range(svr_num):
            dep = vte.get_full_deps()[s]
            sep.guest.execute_ftp(dep.guest, dep.vif.if_addr.ipv4, True)
            sep.guest.execute_ftp(dep.guest, dep.vif.if_addr.ipv6, True)

    elif tool == 'ftp_passive':
        for s in range(svr_num):
            dep = vte.get_full_deps()[s]
            sep.guest.execute_ftp(dep.guest, dep.vif.if_addr.ipv4, False)
            sep.guest.execute_ftp(dep.guest, dep.vif.if_addr.ipv6, False)

def verify_snat_related(vt):
    """ Given a verify topology, execute SNAT ICMP related test. """

    if len(vt.allow) != 1:
        raise "Verify topology is invalid."
    # Flush all conntrack state firstly
    flush_conntrack_on_all_suts()

    nat_spec = NATSpec(_NAT_SERVER_NETV4[_NAT_SNAT_ADDR_IDX_START],
                       _NAT_SERVER_NETV6[_NAT_SNAT_ADDR_IDX_START],
                       1,
                       _NAT_SNAT_PORT_START, 0)

    _nat_setup_flows(vt, 'br0', nat_spec)

    vte = vt.allow[0]
    sep = vte.sep
    # Test servers having different locality
    for dep in vte.get_deps():
        for direction in ["orig", "reply"]:
            for ip_ver in ["ipv4", "ipv6"]:
                _nat_execute_related(nat_spec, sep, dep, ip_ver, direction)

def verify_dnat(vt, tool='telnet', ping_size=1000):
    """ Given a verify topology, execute DNAT test. """

    if len(vt.allow) != 1:
        raise "Verify topology is invalid."

    # flush all conntrack state firstly
    flush_conntrack_on_all_suts()

    # Currently we test DNAT to one server only
    svr_num = 1

    # DNAT only test 1 server which is the 1st dep of the only vte in vt.
    nat_spec = NATSpec(_NAT_SERVER_NETV4[_NAT_ENDPOINT_ADDR_IDX_START],
                       _NAT_SERVER_NETV6[_NAT_ENDPOINT_ADDR_IDX_START],
                       svr_num,
                       0,
                       vipv4=_NAT_ROUTER_CIF_IPV4,
                       vipv6=_NAT_ROUTER_CIF_IPV6)

    _nat_setup_flows(vt, 'br0', nat_spec)

    vte = vt.allow[0]
    sep = vte.sep
    # Must be in sync with vte.get_full_deps() in _nat_configure_vms
    dep = vte.get_full_deps()[0]
    vipv4 = nat_spec.vipv4
    vipv6 = nat_spec.vipv6

    if tool == 'telnet':
        cmd = f"nohup telnet {vipv4} 22 >/dev/null 2>&1 &"
        sep.guest.execute(cmd)
        cmd = f"nohup telnet {vipv6} 22 >/dev/null 2>&1 &"
        sep.guest.execute(cmd)

        _check_nat_result(sep.host, 2, 'tcp')
        sep.guest.kill_process("telnet")
    elif tool == 'ping':
        cmd = f"ping -c 3 -i 0.3 -s {ping_size} {vipv4} >/dev/null 2>&1 &"
        sep.guest.execute(cmd)
        cmd = f"ping -6 -c 3 -i 0.3 -s {ping_size} {vipv6} >/dev/null 2>&1 &"
        sep.guest.execute(cmd)

        _check_nat_result(sep.host, 2, None)
        sep.guest.kill_process("ping")
    elif tool == 'tftp':
        for s in range(svr_num):
            dep = vte.get_full_deps()[s]
            sep.guest.execute_tftp(dep.guest, vipv4)
            sep.guest.execute_tftp(dep.guest, vipv6)

    elif tool == 'ftp_active':
        for s in range(svr_num):
            dep = vte.get_full_deps()[s]
            sep.guest.execute_ftp(dep.guest, vipv4, True)
            sep.guest.execute_ftp(dep.guest, vipv6, True)

    elif tool == 'ftp_passive':
        for s in range(svr_num):
            dep = vte.get_full_deps()[s]
            sep.guest.execute_ftp(dep.guest, vipv4, False)
            sep.guest.execute_ftp(dep.guest, vipv6, False)

def verify_dnat_related(vt):
    """ Given a verify topology, execute DNAT ICMP related test. """

    if len(vt.allow) != 1:
        raise "Verify topology is invalid."

    # Flush all conntrack state firstly
    flush_conntrack_on_all_suts()

    nat_spec = NATSpec(_NAT_SERVER_NETV4[_NAT_ENDPOINT_ADDR_IDX_START],
                       _NAT_SERVER_NETV6[_NAT_ENDPOINT_ADDR_IDX_START],
                       1,
                       0,
                       vipv4=_NAT_ROUTER_CIF_IPV4,
                       vipv6=_NAT_ROUTER_CIF_IPV6)

    _nat_setup_flows(vt, 'br0', nat_spec)

    vte = vt.allow[0]
    sep = vte.sep
    dep = vte.get_full_deps()[0]
    for direction in ["orig", "reply"]:
        for ip_ver in ["ipv4", "ipv6"]:
            _nat_execute_related(nat_spec, sep, dep, ip_ver, direction)
