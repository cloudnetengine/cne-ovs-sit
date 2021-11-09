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
| Library | resources.libraries.python.conntrack
| Library | resources.libraries.python.overlay
| Library | resources.libraries.python.flowutils
| Force Tags | CONNTRACK
| Suite Setup | Run Keywords | Setup Uplink Bridge on All SUTs | br0
| ...         | AND          | Add VIF Ports on All SUTs | br0
| ...         | AND          | Start VMs on All SUTs
| Suite Teardown | Run Keywords | Stop VMs on All SUTs
| ...            | AND          | Teardown Uplink Bridge on All SUTs | br0
| Documentation | *CONNTRACK tests.*


*** Test Cases ***
#| conntrack to controller
#| | [Tags] | CONTROLLER
#| | Flush Conntrack | ${nodes}
#| | Conntrack Test To Controller | ${nodes}

| native conntrack icmp allow all
| | [Tags] | ICMP
| | Setup Default Flows | br0
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br0 | icmp
| | Execute Ping Verification | ${verify_topology}

| native conntrack icmp allow originate
| | [Tags] | ICMP | ALLOW_ORIG
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br0 | icmp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br0 | icmp | ${verify_topology}
| | Execute Ping Verification | ${verify_topology}

| native conntrack tcp allow originate
| | [Tags] | TCP | ALLOW_ORIG
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br0 | tcp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br0 | tcp | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}

| vlan conntrack tcp allow originate
| | [Tags] | VLAN | TCP | ALLOW_ORIG
| | Set Vif Vni By Idx On VM
| | Deploy Vni As VLAN Overlay | br0
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br0 | tcp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br0 | tcp | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}

| vlan conntrack tcp jumbo allow originate
| | [Tags] | VLAN | TCP | JUMBO | ALLOW_ORIG
| | Set VM MTU on All SUTs | 9000
| | Bump Uplink MTU on All SUTs | 9004
| | Set Vif Vni By Idx On VM
| | Deploy Vni As VLAN Overlay | br0
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br0 | tcp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br0 | tcp | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Set VM MTU on All SUTs | 1500
| | Bump Uplink MTU on All SUTs | 1500

| qinq conntrack tcp allow originate
| | [Tags] | QINQ | TCP | ALLOW_ORIG
| | Bump Uplink MTU on All SUTs | 1508
| | Set Vif Vni By Idx On VM
| | Deploy Vni As QINQ Overlay | br0
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br0 | tcp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br0 | tcp | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Bump Uplink MTU on All SUTs | 1500

| qinq conntrack tcp jumbo allow originate
| | [Tags] | QINQ | TCP | JUMBO | ALLOW_ORIG
| | Set VM MTU on All SUTs | 9000
| | Bump Uplink MTU on All SUTs | 9008
| | Set Vif Vni By Idx On VM
| | Deploy Vni As QINQ Overlay | br0
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ACL Setup Allow Proto on All SUTs | br0 | tcp
| | ${verify_topology}= | Run keyword
| | ...                 | ACL Setup Allow Originate | br0 | tcp | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
| | Set VM MTU on All SUTs | 1500
| | Bump Uplink MTU on All SUTs | 1500
