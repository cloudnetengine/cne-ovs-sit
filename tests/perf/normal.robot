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
| Resource | resources/libraries/robot/common.robot
| Library | Collections
| Library | resources.libraries.python.pal
| Library | resources.libraries.python.topology
| Force Tags | PERF | NORMAL
| Suite Setup | Run Keywords | Setup Uplink Bridge on All SUTs | br0
| ...         | AND          | Add VIF Ports on All SUTs | br0
| Suite Teardown | Run Keywords | Teardown Uplink Bridge on All SUTs | br0
| ...            | AND          | Reset Topology
| Documentation | *normal performance test.*

*** Test Cases ***
| Normal offload to offload XHOST
| | [Tags] | NOTNO | XHOST
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | XHOST
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | ${dep}= | Set Variable | ${vte.dep_xhost}[0]
| | Call Method | ${sep.guest} | qemu_start
| | Call Method | ${dep.guest} | qemu_start
| | ${results}= | Run keyword | Execute Performance Test | ${verify_topology}
| | Print Results | ${results}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | qemu_guest_poweroff

| Normal non-offload to non-offload XHOST
| | [Tags] | NOTNO | XHOST
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | XHOST
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | ${dep}= | Set Variable | ${vte.dep_xhost}[0]
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${False}
| | Call Method | ${sep.guest} | qemu_start
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${False}
| | Call Method | ${dep.guest} | qemu_start
| | ${results}= | Run keyword | Execute Performance Test | ${verify_topology}
| | Print Results | ${results}
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${True}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${True}
| | Call Method | ${dep.guest} | qemu_guest_poweroff

| Normal offload to offload NUMA
| | [Tags] | NOTNO | XHOST
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | NUMA
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | ${dep}= | Set Variable | ${vte.dep_numa}[0]
| | Call Method | ${sep.guest} | qemu_start
| | Call Method | ${dep.guest} | qemu_start
| | ${results}= | Run keyword | Execute Performance Test | ${verify_topology}
| | Print Results | ${results}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | qemu_guest_poweroff

| Normal non-offload to non-offload NUMA
| | [Tags] | NOTNO | XHOST
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | NUMA
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | ${dep}= | Set Variable | ${vte.dep_numa}[0]
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${False}
| | Call Method | ${sep.guest} | qemu_start
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${False}
| | Call Method | ${dep.guest} | qemu_start
| | ${results}= | Run keyword | Execute Performance Test | ${verify_topology}
| | Print Results | ${results}
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${True}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${True}
| | Call Method | ${dep.guest} | qemu_guest_poweroff
