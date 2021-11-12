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

"""Defines functions for flow configuration."""

from resources.libraries.python.constants import Constants
from resources.libraries.python.topology import suts

__all__ = [
    u"clear_input_output_flows",
    u"setup_default_pipeline_on_all_suts",
    u"generate_input_flows",
    u"generate_output_flows",
    u"provision_flows",
    u"delete_flows",
]

def _append_as(actions, action):
    if not actions:
        actions = action
    elif action:
        actions = actions + ',' + action
    return actions

def _del_tlv_map(sut, br):
    (ret_code, _, _) = sut.vswitch.execute(f"ovs-ofctl del-tlv-map {br}")
    if int(ret_code) != 0:
        raise RuntimeError('Del tlv map failed')

def _tnl_as(sut, tnl_port, tnl_md):
    actions = ''
    if tnl_port.rip == 'flow':
        for remote_sut in suts:
            if remote_sut == sut:
                continue

            actions = _append_as(actions, r'set_field:{0}-\>tun_dst'.format(
                remote_sut.vswitch.tep_addr.ipv4))

    if tnl_port.vni == 'flow':
        actions = _append_as(actions, r'move:reg0-\>tun_id[0..31]')

    if tnl_md:
        # test tun_metadata0 by provisioning a dynamic value
        actions = _append_as(actions, r'move:reg0-\>tun_metadata0[0..31]')
        # test tun_metadata1 by provisioning a static value
        actions = _append_as(actions,
                             r'set_field:0x1234567890abcdef-\>tun_metadata1')

    actions = _append_as(actions, '{0}'.format(tnl_port.ofp))

    return actions

def _uplink_as(deploy):
    actions = ''
    if deploy == 'vlan':
        actions = r'push_vlan:0x8100,move:reg0[0..11]-\>vlan_tci[0..11],' \
                  r'load:1-\>vlan_tci[12]'
    else:
        # push inner tci then outer tci
        actions = r'push_vlan:0x8100,move:reg0[0..11]-\>vlan_tci[0..11],' \
                  r'load:1-\>vlan_tci[12],' \
                  r'push_vlan:0x88a8,move:reg0[16..27]-\>vlan_tci[0..11],' \
                  r'load:1-\>vlan_tci[12]'
    return actions

def delete_flows(sut, br_name):
    """Delete flows on a bridge.

    :param sut: SUT to delete flows.
    :param br_name: Bridge name.
    :type sut: SUT object
    :type br_name: str
    """
    sut.vswitch.execute(f"ovs-ofctl del-flows {br_name}")

def provision_flows(sut, br_name, flows):
    """Provision flows to a bridge.

    :param sut: SUT to provision flows.
    :param br_name: Bridge name.
    :param flows: Flows to provision.
    :type sut: SUT object
    :type br_name: str
    :type flows: list
    """
    for flow in flows:
        of_ver = ''
        if 'push_vlan' in flow:
            of_ver = '-O OpenFlow13'

        sut.vswitch.execute(f"ovs-ofctl {of_ver} add-flow {br_name} {flow}")

    sut.vswitch.execute(f"ovs-ofctl dump-flows {br_name}")

def clear_input_output_flows(sut, br_name):
    """Clear flows of INPUT/OUTPUT tables on a bridge.
    This is used in case default INPUT/OUTPUT tables need to be re-implemented,
    like for overlay logic.

    :param sut: SUT to delete flows.
    :param br_name: Bridge name.
    :type sut: SUT object
    :type br_name: str
    """
    sut.vswitch.execute(f"ovs-ofctl del-flows {br_name} table={Constants.OF_TABLE_INPUT}")
    sut.vswitch.execute(f"ovs-ofctl del-flows {br_name} table={Constants.OF_TABLE_OUTPUT}")

def generate_output_flows(sut, br_name, deploy, tnl_md=False):
    """Generate flows of OUTPUT table on a bridge.

    :param sut: SUT to delete flows.
    :param br_name: Bridge name.
    :param deploy: Deployment type, can be native, tnl, vlan, or qinq.
    :param tnl_md: Tunnel metadata is enabled or not.
    :type sut: SUT object
    :type br_name: str
    :type deploy: str
    :type tnl_md: bool
    :returns: Generated OUTPUT table flows.
    :rtype: list
    """

    if deploy not in ('tnl', 'vlan', 'qinq', 'native'):
        raise RuntimeError(f"setup output flows for {deploy} is invalid")

    flows = list()
    br = sut.vswitch.get_bridge(br_name)
    ########################### generate flooding start ####################
    vnis = br.vnis
    for vni in vnis.keys():
        ##################### building flooding flows for each vni
        # and flooding flows all have priority '100'

        # counting all local vif ports on the vni
        # There is one assumption that 'uplinks' are always attached
        # to physical bridge in 'tnl' mode.
        local_ofps = []
        for vif in vnis[vni]:
            local_ofps.append(vif.ofp)
        if not local_ofps:
            raise RuntimeError('no local vif on vni:{0}'.format(vni))

        ########### generate flows originated from each local vif
        for local_ofp in local_ofps:
            output_as = ''
            # always flood to local vifs before external ports
            for ofp in local_ofps:
                if ofp == local_ofp:
                    continue
                output_as = _append_as(output_as, '{0}'.format(ofp))

            if deploy == 'tnl':
                for tnl_port in br.tnl_ports:
                    # filter out unrrelevant tunnel ports
                    if tnl_port.vni != 'flow' and tnl_port.vni != vni:
                        continue

                    output_as = _append_as(output_as,
                                           _tnl_as(sut, tnl_port, tnl_md))
            elif deploy in ('vlan', 'qinq'):
                # do push actions for all uplinks one time
                output_as = _append_as(output_as, _uplink_as(deploy))

                for uplink in br.uplinks:
                    output_as = _append_as(output_as, '{0}'.format(uplink.ofp))
            else:
                # native
                for uplink in br.uplinks:
                    output_as = _append_as(output_as, '{0}'.format(uplink.ofp))

            # 'reg1=0' meaning no FIB match
            flows.append('table={0},in_port={1},reg1=0,'
                         'priority=100,action={2}'
                         .format(Constants.OF_TABLE_OUTPUT,
                                 local_ofp, output_as))

        ########### generate flows originated from external ports,
        # i.e. tnl/uplink ports
        # we don't forward the pkt back to external port in this case
        output_as = ''
        for local_ofp in local_ofps:
            output_as = _append_as(output_as, '{0}'.format(local_ofp))
        if not output_as:
            raise RuntimeError('we cannot have empty local vifs: {0}'.format(local_ofps))

        if deploy == 'tnl':
            for tnl_port in br.tnl_ports:
                if tnl_md:
                    # in case tnl with metadata, we add those into match
                    flows.append(f"table={Constants.OF_TABLE_OUTPUT},"\
                                 f"in_port={tnl_port.ofp},reg0={vni},reg1=0,"\
                                 f"tun_metadata0={vni},"\
                                 f"tun_metadata1=0x1234567890abcdef,"\
                                 f"priority=100,action={output_as}")
                else:
                    flows.append(f"table={Constants.OF_TABLE_OUTPUT},"\
                                 f"in_port={tnl_port.ofp},reg0={vni},reg1=0,"\
                                 f"priority=100,action={output_as}")
        elif deploy in ('vlan', 'qinq'):
            for uplink in br.uplinks:
                # we only take the first 12 bits to match vni for vlan/qinq
                flows.append(f"table={Constants.OF_TABLE_OUTPUT},"\
                             f"in_port={uplink.ofp},reg0[0..11]={vni},reg1=0,"\
                             f"priority=100,action={output_as}")
        else:
            # native
            for uplink in br.uplinks:
                flows.append(f"table={Constants.OF_TABLE_OUTPUT},"\
                             f"in_port={uplink.ofp},reg1=0,"\
                             f"priority=100,action={output_as}")
    ########################### generate flooding end ######################

    ########################### generate unicast start #####################
    # output to definitive dst port, i.e. reg1 is non zero
    # 1. tnl/uplink ports need special actions like:
    #    - set tunnel meta data
    #    - push vlan headers
    #
    # using priority '20' than '10' in case 2.
    if deploy == 'tnl':
        # generate unicast flow for each tnl_port by matching reg1
        for tnl_port in br.tnl_ports:
            output_as = _tnl_as(sut, tnl_port, tnl_md)
            flows.append('table={0},reg1={1},priority=20,action={2}'
                         .format(Constants.OF_TABLE_OUTPUT,
                                 tnl_port.ofp, output_as))
    elif deploy in ('vlan', 'qinq'):
        # generate unicast flow for each uplink by matching reg1
        output_as = _uplink_as(deploy)
        for uplink in br.uplinks:
            flows.append('table={0},reg1={1},priority=20,action={2},{3}'
                         .format(Constants.OF_TABLE_OUTPUT,
                                 uplink.ofp, output_as, uplink.ofp))
    else:
        # native
        for uplink in br.uplinks:
            flows.append('table={0},reg1={1},priority=20,action={2}'
                         .format(Constants.OF_TABLE_OUTPUT,
                                 uplink.ofp, uplink.ofp))

    # 2. forwarding to vif port
    if tnl_md:
        # 2.1 for unicast from tnl with md, we setup flows to check
        # tnl metadata correctness, with priority '15'
        for tnl_port in br.tnl_ports:
            # we don't have a good way to check tun_metadata0 as
            # 'tun_metadata0=reg0' doesn't work, so add check for each vni
            for vni in vnis.keys():
                # note:
                # 'action=output:reg1' works but not 'action:reg1'
                flows.append('table={0},in_port={1},'
                             'tun_metadata0={2},tun_metadata1=0x1234567890abcdef,'
                             'priority=15,action=output:reg1'
                             .format(Constants.OF_TABLE_OUTPUT,
                                     tnl_port.ofp, vni))

    # 2.2 those flows are with the lowest priority
    for vif in br.vifs:
        flows.append('table={0},reg1={1},priority=10,action={2}'
                     .format(Constants.OF_TABLE_OUTPUT,
                             vif.ofp, vif.ofp))
    ########################### generate unicast end #######################
    return flows

def generate_input_flows(sut, br_name, deploy):
    """Generate flows of INPUT table on a bridge.
    setup flows for table INPUT which mainly
    - loading 'virtual network' id into reg0
    - then goto ACL table

    :param sut: SUT to delete flows.
    :param br_name: Bridge name.
    :param deploy: Deployment type, can be native, tnl, vlan, or qinq.
    :type sut: SUT object
    :type br_name: str
    :type deploy: str
    :returns: Generated INPUT table flows.
    :rtype: list
    """
    flows = list()
    if deploy == 'native':
        flows.append(f"table={Constants.OF_TABLE_INPUT},priority=100," \
                     f"action=goto_table:{Constants.OF_TABLE_ACL}")
        return flows

    br = sut.vswitch.get_bridge(br_name)
    for vif in br.vifs:
        if deploy == 'qinq':
            # using 'vni' as inner tci in reg0[0..11]
            # and 'vni + 100' as outer tci in reg0[16..27]
            flows.append(f"table={Constants.OF_TABLE_INPUT},"\
                         f"in_port={vif.ofp},priority=100," \
                         f"action=load:{vif.vni}-\\>reg0[0..11]," \
                         f"load:{vif.vni + 100}-\\>reg0[16..27]," \
                         f"goto_table:{Constants.OF_TABLE_ACL}")
        else:
            flows.append(f"table={Constants.OF_TABLE_INPUT},"\
                         f"in_port={vif.ofp},priority=100," \
                         f"action=load:{vif.vni}-\\>reg0[0..31],"\
                         f"goto_table:{Constants.OF_TABLE_ACL}")

    if deploy == 'tnl':
        for tnl_port in br.tnl_ports:
            # note:
            # - we have to use 'move' instead of 'load' which requires the
            #   source must be an literal value.
            # - 'load' in 'learn' action can do more thing than normal 'load'
            flows.append(f"table={Constants.OF_TABLE_INPUT},"\
                         f"in_port={tnl_port.ofp},priority=100,"\
                         f"action=move:tun_id[0..31]-\\>reg0[0..31],"\
                         f"goto_table:{Constants.OF_TABLE_ACL}")
    elif deploy == 'vlan':
        for uplink in br.uplinks:
            flows.append(f"table={Constants.OF_TABLE_INPUT},"\
                         f"in_port={uplink.ofp},priority=100,"\
                         f"action=move:vlan_tci[0..11]-\\>reg0[0..11],"\
                         f"pop_vlan,goto_table:{Constants.OF_TABLE_ACL}")
    elif deploy == 'qinq':
        for uplink in br.uplinks:
            # outer tci in reg0[16..27]
            # inner tci in reg0[0..11]
            flows.append(f"table={Constants.OF_TABLE_INPUT},"\
                         f"in_port={uplink.ofp},priority=100,"\
                         f"action=move:vlan_tci[0..11]-\\>reg0[16..27],pop_vlan,"
                         f"move:vlan_tci[0..11]-\\>reg0[0..11],pop_vlan,"
                         f"goto_table:{Constants.OF_TABLE_ACL}")
    return flows

def setup_default_pipeline_on_all_suts(br_name):
    """Setup default pipeline for the bridges.
    Currently overlay and NAT logics are based on this pipeline.
    The stages are: ADMISS/INPUT/ACL/CORE/FIB/NAT/L2_MATCH/OUTPUT.

    :param br_name: Bridge name.
    :type br_name: str
    """
    for sut in suts:
        # clear all existing flows firstly
        sut.vswitch.execute(f"ovs-ofctl del-flows {br_name}")

        flows = list()

        ########## setup flows for table ADMISS
        flows.append(f"table={Constants.OF_TABLE_ADMISS},"
                     f"priority=100,action=goto_table:{Constants.OF_TABLE_INPUT}")

        ########## setup flows for table INPUT
        flows.extend(generate_input_flows(sut, br_name, 'native'))

        ########## setup flows for table ACL
        # just goto CORE table unconditionaly,
        # ACL test cases is going to rewrite this table
        flows.append(f"table={Constants.OF_TABLE_ACL},priority=1,action=drop")
        flows.append(f"table={Constants.OF_TABLE_ACL},priority=100,"
                     f"action=goto_table:{Constants.OF_TABLE_CORE}")

        ########## setup flows for table CORE
        # setup flows for table CORE which is doing:
        # - populate FIB table based on NXM_NX_REG0/src mac/src port
        # - lookup dst port in FIB table and put to NXM_NX_REG1
        # - resubmit to OUTPUT table
        flows.append(f"table={Constants.OF_TABLE_CORE},"
                     f"actions=learn\\(table={Constants.OF_TABLE_FIB},"
                     f"NXM_NX_REG0[0..31],NXM_OF_ETH_DST[]=NXM_OF_ETH_SRC[],"
                     f"load:NXM_OF_IN_PORT[]-\\>NXM_NX_REG1[0..15]\\),"
                     f"goto_table:{Constants.OF_TABLE_NAT}")

        flows.append(f"table={Constants.OF_TABLE_NAT},"
                     f"action=goto_table:{Constants.OF_TABLE_L2_MATCH}")

        flows.append(f"table={Constants.OF_TABLE_L2_MATCH},"
                     f"actions=resubmit\\(,{Constants.OF_TABLE_FIB}\\),"
                     f"resubmit\\(,{Constants.OF_TABLE_OUTPUT}\\)")

        ########## setup flows for table CORE
        flows.extend(generate_output_flows(sut, br_name, 'native', False))

        # provision the flows
        provision_flows(sut, br_name, flows)
