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

"""Library for conntrack based ACL."""

from resources.libraries.python.topology import suts
from resources.libraries.python.constants import Constants
from resources.libraries.python.flowutils import provision_flows
from resources.libraries.python.pal import verify_topology_allow_originate

__all__ = [
    u"acl_setup_allow_proto_on_all_suts",
    u"acl_setup_allow_originate",
]

def _generate_flow_track_proto(vni, ofp, proto):
    # for ipv6 fragmentation, its original l4 proto is only parsed for the
    # 1st frag, and the proto is not parsed by cdp, i.e. miniflow_extract()
    # using IPPROTO_FRAGMENT as nw_proto for 'later' frags, so we have to
    # add a rule to make it go through conntrack, also meaning defrag logic.
    # for ipv4 fragmentation, it's different than ipv4 as l4 proto is parsed
    # for all frags, i.e. the 1st and 'later' frags.

    # note for 'ct_state=-trk' flows, we must using 'zone=reg0[0..15]'
    # for 'ct' action to load 'zone' from the flow under processing.
    # this is very important for ports (tnl/uplink) which can multiplex
    # many zones.
    # if we use 'zone=vni' in this case, only the last vni is taking into
    # effect as those flows matching criteria are the same, meaning traffic
    # on a zone will be marked with the wrong zone if there are more than
    # one vnis. we observed that in vlan/conntrack test, a uplink recv
    # one pkt with vlan tci 100, while doing ct with zone=101
    #
    # one side note is that it seems that using ovs-ofctl provisioning
    # the same flow more than once won't have any error returned.
    # because if we have more than 1 vnis, those 'ct_state=-trk' flows
    # are going to be configured more than once, and it seems no problem.
    flows = list()
    flows.append(f"table={Constants.OF_TABLE_ACL},"\
                 f"in_port={ofp},priority=100,ipv6,ip_frag=later," \
                 f"ct_state=-trk,action=ct\\(zone=reg0[0..15],"\
                 f"table={Constants.OF_TABLE_ACL}\\)")
    protos = list()
    if proto == 'udp':
        # iperf udp test needs tcp to setup testing ports/connections
        protos = ['tcp', 'tcp6', 'udp', 'udp6']
    else:
        protos = [proto, '{0}6'.format(proto)]
    for p in protos:
        flows.append(f"table={Constants.OF_TABLE_ACL},"\
                     f"in_port={ofp},priority=100,{p},ct_state=-trk,"\
                     f"action=ct\\(zone=reg0[0..15],table={Constants.OF_TABLE_ACL}\\)")
        flows.append(f"table={Constants.OF_TABLE_ACL},"\
                     f"in_port={ofp},priority=100,{p},ct_zone={vni},"\
                     f"ct_state=+trk+new,action=ct\\(commit,zone={vni}\\),"\
                     f"goto_table:{Constants.OF_TABLE_CORE}")
        flows.append(f"table={Constants.OF_TABLE_ACL},"\
                     f"in_port={ofp},priority=100,{p},ct_zone={vni},"\
                     f"ct_state=+trk+est,"\
                     f"action=goto_table:{Constants.OF_TABLE_CORE}")
        flows.append(f"table={Constants.OF_TABLE_ACL},"\
                     f"in_port={ofp},priority=100,{p},ct_zone={vni},"\
                     f"ct_state=+trk+est+rpl,"\
                     f"action=goto_table:{Constants.OF_TABLE_CORE}")
    return flows

def acl_setup_allow_proto_on_all_suts(br_name, proto):
    """Setup acl flows to allow proto for the bridges.

    :param br_name: Bridge name.
    :param proto: Allowed protocol.
    :type br_name: str
    :type proto: str
    """
    for sut in suts:
        # clear all existing flows firstly
        sut.vswitch.execute(f"ovs-ofctl del-flows {br_name} "
                            f"table={Constants.OF_TABLE_ACL}")

        flows = list()

        flows.append('table={0},priority=1,action=drop'.format(
            Constants.OF_TABLE_ACL))

        # setup default allowed arp/nd flows as the highest priority
        # always allow arp
        flows.append(f"table={Constants.OF_TABLE_ACL},priority=2000,arp,"\
                     f"action=goto_table:{Constants.OF_TABLE_CORE}")
        # always allow nd
        flows.append(f"table={Constants.OF_TABLE_ACL},priority=2000,"\
                     f"icmp6,icmp_type=135,"\
                     f"action=goto_table:{Constants.OF_TABLE_CORE}")
        flows.append(f"table={Constants.OF_TABLE_ACL},priority=2000,"\
                     f"icmp6,icmp_type=136,"\
                     f"action=goto_table:{Constants.OF_TABLE_CORE}")

        flow_gen_func = _generate_flow_track_proto
        br = sut.vswitch.get_bridge(br_name)
        # for flows from vifs
        vnis = br.vnis
        for vni in vnis.keys():
            for vif in vnis[vni]:
                flows.extend(flow_gen_func(vni, vif.ofp, proto))

        # for flows from trunk ports, i.e. uplink or tnl_port
        for vni in vnis.keys():
            for tnl_port in br.tnl_ports:
                flows.extend(flow_gen_func(vni, tnl_port.ofp, proto))
            for uplink in br.uplinks:
                flows.extend(flow_gen_func(vni, uplink.ofp, proto))

        # provision the flows
        provision_flows(sut, br_name, flows)

def acl_setup_allow_originate(br_name, proto, vt):
    """Given a verify topology, construct a new verify topology to
    allow 'proto' traffic from a source endpoint A, and deny other
    'proto' traffic initiated from other endpoint to A.

    :param br_name: Bridge name.
    :param proto: Allowed protocol.
    :param vt: Verify topology.
    :type br_name: str
    :type proto: str
    :type vt: VerifyTopology obj
    :returns: New verify topology.
    :rtype: VerifyTopology obj
    """

    (sep, new_vt) = verify_topology_allow_originate(vt)
    vif = sep.vif

    flows = list()
    # Match on dl_dst, as all vnics has different mac in our tests
    protos = [proto, f"{proto}6"]
    for p in protos:
        flows.append(f"table={Constants.OF_TABLE_ACL},priority=2000,"\
                     f"ct_state=+trk+new,dl_dst={vif.mac},{p},action=drop")
        flows.append(f"table={Constants.OF_TABLE_ACL},priority=2000,"\
                     f"ct_state=+trk+inv,dl_dst={vif.mac},{p},action=drop")
    provision_flows(sep.host, br_name, flows)

    return new_vt
