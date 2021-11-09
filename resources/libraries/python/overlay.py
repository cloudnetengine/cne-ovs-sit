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

"""Defines functions for overlay deployment."""

from resources.libraries.python.constants import Constants
from resources.libraries.python.topology import suts
from resources.libraries.python.flowutils import delete_flows, \
                                                 clear_input_output_flows, \
                                                 generate_input_flows, \
                                                 generate_output_flows, \
                                                 provision_flows, \
                                                 setup_default_pipeline_on_all_duts

__all__ = [
    u"set_vif_vni_by_idx_on_vm",
    u"set_vif_vni_by_idx_on_host",
    u"reset_vif_vni_on_all_suts",
    u"deploy_vni_as_tunnel_overlay",
    u"undeploy_vni_as_tunnel_overlay",
    u"deploy_vni_as_vlan_overlay",
    u"undeploy_vni_as_vlan_overlay",
    u"deploy_vni_as_qinq_overlay",
    u"undeploy_vni_as_qinq_overlay",
]

_VNI_BASE_BY_IDX_ON_VM = 200
_VNI_BASE_BY_IDX_ON_HOST = 300

def _add_tlv_map(sut, br_name):
    (ret_code, _, _) = sut.vswitch.execute('ovs-ofctl add-tlv-map {0} ' \
          '\"{{class=0xffff,type=0,len=4}}->tun_metadata0,' \
          '{{class=0xffff,type=1,len=8}}->tun_metadata1\"'.format(br_name))
    if int(ret_code) != 0:
        raise RuntimeError('Add tlv map failed')

def _del_tlv_map(sut, br_name):
    (ret_code, _, _) = sut.vswitch.execute(f"ovs-ofctl del-tlv-map {br_name}")
    if int(ret_code) != 0:
        raise RuntimeError('Add tlv map failed')

def _delete_tunnel_ports(br_name):
    for sut in suts:
        br = sut.vswitch.get_bridge(br_name)
        for tnl_port in br.tnl_ports:
            sut.vswitch.delete_tunnel_port(br_name, tnl_port)

def _create_tunnel_ports(br_name, tnl_type, rip_mode, vni_mode):
    for sut in suts:
        br = sut.vswitch.get_bridge(br_name)
        if rip_mode != 'flow':
            for remote_sut in suts:
                if remote_sut == sut:
                    continue

                if vni_mode != 'flow':
                    for vni in br.vnis.keys():
                        sut.vswitch.create_tunnel_port(br_name, tnl_type,
                                                       remote_sut.vswitch.tep_addr.ipv4, vni)
                else:
                    sut.vswitch.create_tunnel_port(br_name, tnl_type,
                                                   remote_sut.vswitch.tep_addr.ipv4, 'flow')

        elif vni_mode != 'flow':
            for vni in br.vnis.keys():
                sut.vswitch.create_tunnel_port(br_name, tnl_type, 'flow', vni)
        else:
            sut.vswitch.create_tunnel_port(br_name, tnl_type, 'flow', 'flow')

def _overlay_flow_clear(br_name):
    for sut in suts:
        delete_flows(sut, br_name)

        # tlv_map must be deleted after flow deletion, as active flows
        # might reference the map.
        # https://mail.openvswitch.org/pipermail/ovs-dev/2017-March/329815.html
        br = sut.vswitch.get_bridge(br_name)
        if br.with_md:
            _del_tlv_map(sut, br_name)
            br.with_md = False

def _tunnel_overlay_flow_setup(br_name, with_md=False):
    for sut in suts:
        br = sut.vswitch.get_bridge(br_name)
        if with_md:
            _add_tlv_map(sut, br_name)
            br.with_md = True

        clear_input_output_flows(sut, br_name)

        flows = list()
        # setup input flows for provisioning reg0
        flows.extend(generate_input_flows(sut, br_name, 'tnl'))

        # setup output flows for tnl deployment
        flows.extend(generate_output_flows(sut, br_name, 'tnl', with_md))

        # provision the flows
        provision_flows(sut, br_name, flows)

def _l2_overlay_flow_setup(br_name, mode='vlan'):
    for sut in suts:
        clear_input_output_flows(sut, br_name)

        flows = list()
        # setup input flows for provisioning reg0
        flows.extend(generate_input_flows(sut, br_name, mode))

        # setup output flows for tnl deployment
        flows.extend(generate_output_flows(sut, br_name, mode))

        # provision the flows
        provision_flows(sut, br_name, flows)

def set_vif_vni_by_idx_on_vm():
    """Assign VNIs to VIFs according to a VIF's index on the VM."""

    for sut in suts:
        for vm in sut.vms:
            vni_idx = _VNI_BASE_BY_IDX_ON_VM
            for vif in vm.vifs:
                vif.vni = f"{vni_idx}"
                vni_idx += 1
        sut.vswitch.refresh_bridge_vnis()

def set_vif_vni_by_idx_on_host():
    """Assign VNIs to VIFs according to a VIF's index on the host."""

    for sut in suts:
        vni_idx = _VNI_BASE_BY_IDX_ON_HOST
        for vm in sut.vms:
            for vif in vm.vifs:
                vif.vni = f"{vni_idx}"
                vni_idx += 1
        sut.vswitch.refresh_bridge_vnis()

def reset_vif_vni_on_all_suts():
    """Clear VIF's VNI."""

    for sut in suts:
        for vm in sut.vms:
            for vif in vm.vifs:
                vif.vni = f"{Constants.VNI_NONE}"
        sut.vswitch.refresh_bridge_vnis()

def deploy_vni_as_tunnel_overlay(br_name, tnl_type, rip_mode='flow',
                                 tun_id_mode='flow', tnl_md=False):
    """Deploy tunnel based overlay according to VIFs' VNI configuration.

    :param br_name: Bridge name for VIF attachment, i.e. integration bridge.
    :param tnl_type: Tunnel type.
    :param rip_mode: Remote IP address mode. 'flow' means rip will be dynamically
        set by a flow tunnel set action, so a tunnel port can be multiplexed
        by multiple tunnels to different remote peers. Otherwise "non-flow" means
        rip will be explicitly configured for each remote peer.
    :param tun_id_mode: Tunnel id mode. 'flow' means tun_id will be dynamically
        set by a flow tunnel set action, so a tunnel port can be multiplexed
        by multiple overlays. Otherwise 'non-flow' means tun_id will be explicitly
        configured for each overly.
    :param tun_md: Using tunnel metadata. Only applicable to GENEVE tnl_type.
    :type br_name: str
    :type tnl_type: str
    :type rip_mode: str
    :type tnl_id_mode: str
    :type tnl_md: bool
    """
    _create_tunnel_ports(br_name, tnl_type, rip_mode, tun_id_mode)
    setup_default_pipeline_on_all_duts(br_name)
    _tunnel_overlay_flow_setup(br_name, tnl_md)

def undeploy_vni_as_tunnel_overlay(br_name):
    """Undeply tunnel based overlay.
    :param br_name: Bridge name for VIF attachment, i.e. integration bridge.
    :type br_name: str
    """
    _overlay_flow_clear(br_name)
    _delete_tunnel_ports(br_name)

def deploy_vni_as_vlan_overlay(br_name):
    """Deploy vlan based overlay according to VIFs' VNI configuration.

    :param br_name: Bridge name for VIF attachment, i.e. integration bridge.
    :type br_name: str
    """
    setup_default_pipeline_on_all_duts(br_name)
    _l2_overlay_flow_setup(br_name, 'vlan')

def undeploy_vni_as_vlan_overlay(br_name):
    """Undeply vlan based overlay.
    :param br_name: Bridge name for VIF attachment, i.e. integration bridge.
    :type br_name: str
    """
    _overlay_flow_clear(br_name)

def deploy_vni_as_qinq_overlay(br_name):
    """Deploy QinQ based overlay according to VIFs' VNI configuration.

    :param br_name: Bridge name for VIF attachment, i.e. integration bridge.
    :type br_name: str
    """
    for sut in suts:
        sut.vswitch.set_vlan_limit(2)
    setup_default_pipeline_on_all_duts(br_name)
    _l2_overlay_flow_setup(br_name, 'qinq')

def undeploy_vni_as_qinq_overlay(br_name):
    """Undeply QinQ based overlay.
    :param br_name: Bridge name for VIF attachment, i.e. integration bridge.
    :type br_name: str
    """
    for sut in suts:
        sut.vswitch.set_vlan_limit(2)
        sut.vswitch.set_uplink_mtu(mtu=1500)
    _overlay_flow_clear(br_name)
