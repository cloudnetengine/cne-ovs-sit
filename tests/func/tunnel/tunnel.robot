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

*** Settings ***
| Library | resources.libraries.python.pal
| Library | resources.libraries.python.overlay
| Library | resources.libraries.python.conntrack
| Force Tags | TUNNEL
| Suite Setup | Run Keywords | Setup Uplink Bridge on All SUTs | br0
| ...         | AND          | Bump Uplink MTU on All SUTs | 1600
| ...         | AND          | Create Bridge on All SUTs | br-int
| ...         | AND          | Add VIF Ports on All SUTs | br-int
| ...         | AND          | Start VMs on All SUTs
| Suite Teardown | Run Keywords | Stop VMs on All SUTs
| ...            | AND          | Delete Bridge on All SUTs | br-int
| ...            | AND          | Teardown Uplink Bridge on All SUTs | br0
| Documentation | *TUNNEL tests.*


*** Test Cases ***
| VXLAN VIF VNI by idx on Host test remote_ip:flow tun_id:flow
| | [Tags] | VXLAN
| | Set Vif Vni By Idx On Host
| | Deploy Vni As Tunnel Overlay | br-int | vxlan
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| VXLAN VIF VNI by idx on VM test remote_ip:flow tun_id:flow
| | [Tags] | VXLAN
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | vxlan
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| VXLAN VIF VNI by idx on Host test remote_ip:non-flow tun_id:flow
| | [Tags] | VXLAN
| | Set Vif Vni By Idx On Host
| | Deploy Vni As Tunnel Overlay | br-int | vxlan | rip=non-flow
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| VXLAN VIF VNI by idx on VM test remote_ip:non-flow tun_id:flow
| | [Tags] | VXLAN
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | vxlan | rip=non-flow
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| VXLAN VIF VNI by idx on Host test remote_ip:flow tun_id:non-flow
| | [Tags] | VXLAN
| | Set Vif Vni By Idx On Host
| | Deploy Vni As Tunnel Overlay | br-int | vxlan | rip=flow | tun_id=non-flow
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| VXLAN VIF VNI by idx on VM test remote_ip:flow tun_id:non-flow
| | [Tags] | VXLAN
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | vxlan | rip=flow | tun_id=non-flow
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| VXLAN VIF VNI by idx on Host test remote_ip:non-flow tun_id:non-flow
| | [Tags] | VXLAN
| | Set Vif Vni By Idx On Host
| | Deploy Vni As Tunnel Overlay | br-int | vxlan | rip=non-flow | tun_id=non-flow
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| VXLAN VIF VNI by idx on VM test remote_ip:non-flow tun_id:non-flow
| | [Tags] | VXLAN
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | vxlan | rip=non-flow | tun_id=non-flow
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
#| | Undeploy Vni As Tunnel Overlay | br-int
#| | Reset Vif Vni on All SUTs

| VXLAN TEP with VLAN test
| | [Tags] | VXLAN
| | Set Port VLAN on All SUTs | br0 | 15
| | Set Vif Vni By Idx On Host
| | Deploy Vni As Tunnel Overlay | br-int | vxlan
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs
| | Set Port VLAN on All SUTs | br0 | 0

| GRE VIF VNI by idx on VM test remote_ip:flow tun_id:flow
| | [Tags] | GRE
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | gre
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| GENEVE VIF VNI by idx on VM test remote_ip:flow tun_id:flow
| | [Tags] | GENEVE
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| GENEVE MD VIF VNI by idx on VM test remote_ip:flow tun_id:flow
| | [Tags] | GENEVE
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve | tnl_md=True
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| GENEVE MD conntrack icmp allow all test remote_ip:non-flow tun_id:flow
| | [Tags] | GENEVE | CONNTRACK
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve | rip=non-flow | tun_id=flow | tnl_md=True
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br-int | icmp
| | Execute Ping Verification | ${verify_topology}
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| GENEVE MD conntrack icmp originate test remote_ip:non-flow tun_id:flow
| | [Tags] | GENEVE | CONNTRACK | ALLOW_ORIG
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve | rip=non-flow | tun_id=flow | tnl_md=True
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br-int | icmp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br-int | icmp | ${verify_topology}
| | Execute Ping Verification | ${verify_topology}
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| GENEVE MD conntrack tcp allow all test remote_ip:non-flow tun_id:flow
| | [Tags] | GENEVE | CONNTRACK
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve | rip=non-flow | tun_id=flow | tnl_md=True
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br-int | tcp
| | Execute iperf Verification | ${verify_topology}
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| GENEVE MD conntrack tcp originate test remote_ip:non-flow tun_id:flow
| | [Tags] | GENEVE | CONNTRACK | ALLOW_ORIG
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve | rip=non-flow | tun_id=flow | tnl_md=True
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br-int | tcp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br-int | tcp | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| GENEVE MD conntrack udp allow all test remote_ip:non-flow tun_id:flow
| | [Tags] | GENEVE | CONNTRACK
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve | rip=non-flow | tun_id=flow | tnl_md=True
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br-int | udp
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| GENEVE MD conntrack udp originate test remote_ip:non-flow tun_id:flow
| | [Tags] | GENEVE | CONNTRACK | ALLOW_ORIG
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve | rip=non-flow | tun_id=flow | tnl_md=True
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br-int | udp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br-int | udp | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs

| GENEVE MD conntrack tcp originate jumbo test remote_ip:non-flow tun_id:flow
| | [Tags] | GENEVE | TCP | CONNTRACK | ALLOW_ORIG | JUMBO
| | Set VM MTU on All SUTs | 9000
| | Bump Uplink MTU on All SUTs | 9100
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve | rip=non-flow | tun_id=flow | tnl_md=True
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br-int | tcp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br-int | tcp | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs
| | Bump Uplink MTU on All SUTs | 1600

| GENEVE MD conntrack udp originate jumbo test remote_ip:non-flow tun_id:flow
| | [Tags] | GENEVE | UDP | CONNTRACK | ALLOW_ORIG | JUMBO
| | Set VM MTU on All SUTs | 9000
| | Bump Uplink MTU on All SUTs | 9100
| | Set Vif Vni By Idx On VM
| | Deploy Vni As Tunnel Overlay | br-int | geneve | rip=non-flow | tun_id=flow | tnl_md=True
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br-int | udp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br-int | udp | ${verify_topology}
| | Execute iperf Verification | ${verify_topology} | proto=udp
| | Undeploy Vni As Tunnel Overlay | br-int
| | Reset Vif Vni on All SUTs
| | Bump Uplink MTU on All SUTs | 1600
