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

# Only test lacp bond for now. Could be extended for other mode.
*** Settings ***
| Library | Collections
| Library | resources.libraries.python.pal
| Force Tags | BOND
| Suite Setup | Run Keywords | Setup Uplink Bridge on All SUTs | br0 | bond=${True}
| ...         | AND          | Add VIF Ports on All SUTs | br0
| ...         | AND          | Start VMs on All SUTs
| Suite Teardown | Run Keywords | Stop VMs on All SUTs
| ...            | AND          | Teardown Uplink Bridge on All SUTs | br0
| Documentation | *vSwitch Bond test.*

*** Test Cases ***
| Bond icmp test
| | [Tags] | PING
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}

| Bond icmp fail over test
| | [Tags] | PING
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | XHOST
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${0} | up=${False}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${1} | up=${True}
| | Sleep | 5s
| | Execute Ping Verification | ${verify_topology}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${0} | up=${True}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${1} | up=${False}
| | Sleep | 5s
| | Execute Ping Verification | ${verify_topology}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${0} | up=${False}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${1} | up=${False}
| | Sleep | 5s
| | Run keyword | Verify Topology Change Allow to Deny | ${verify_topology}
| | Execute Ping Verification | ${verify_topology}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${0} | up=${True}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${1} | up=${True}
| | Sleep | 5s
| | Run keyword | Verify Topology Change Deny to Allow | ${verify_topology}
| | Execute Ping Verification | ${verify_topology}

| bond iperf test
| | [Tags] | IPERF
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute iperf Verification | ${verify_topology}

| Bond iperf fail over test
| | [Tags] | IPERF
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | XHOST
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${0} | up=${False}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${1} | up=${True}
| | Sleep | 5s
| | Execute Iperf Verification | ${verify_topology}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${0} | up=${True}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${1} | up=${False}
| | Sleep | 5s
| | Execute Iperf Verification | ${verify_topology}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${0} | up=${False}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${1} | up=${False}
| | Sleep | 5s
| | Run keyword | Verify Topology Change Allow to Deny | ${verify_topology}
| | Execute Iperf Verification | ${verify_topology}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${0} | up=${True}
| | Call Method | ${sep.host.vswitch} | set_bond_member_up | br0 | ${1} | up=${True}
| | Sleep | 5s
| | Run keyword | Verify Topology Change Deny to Allow | ${verify_topology}
| | Execute iperf Verification | ${verify_topology}
