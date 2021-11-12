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
| Library | Collections
| Library | resources.libraries.python.pal
| Library | resources.libraries.python.topology
| Force Tags | VIRTIO
| Suite Setup | Run Keywords | Setup Uplink Bridge on All SUTs | br0
| ...         | AND          | Add VIF Ports on All SUTs | br0
| Suite Teardown | Run Keyword | Teardown Uplink Bridge on All SUTs | br0
| Documentation | *VIRTIO test.*

*** Test Cases ***
| virtio offload to non-offload NUMA
| | [Tags] | OTNO | NUMA
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | NUMA
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | ${dep}= | Set Variable | ${vte.dep_numa}[0]
| | Call Method | ${sep.guest} | qemu_start
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${False}
| | Call Method | ${dep.guest} | qemu_start
| | Execute iperf Verification | ${verify_topology}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${True}
| | Call Method | ${dep.guest} | qemu_guest_poweroff

| virtio non-offload to non-offload NUMA
| | [Tags] | NOTNO | NUMA
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
| | Execute iperf Verification | ${verify_topology}
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${True}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${True}
| | Call Method | ${dep.guest} | qemu_guest_poweroff

| virtio non-offload to offload NUMA
| | [Tags] | NOTO | NUMA
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | NUMA
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | ${dep}= | Set Variable | ${vte.dep_numa}[0]
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${False}
| | Call Method | ${sep.guest} | qemu_start
| | Call Method | ${dep.guest} | qemu_start
| | Execute iperf Verification | ${verify_topology}
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${True}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | qemu_guest_poweroff

| virtio offload to non-offload XHOST
| | [Tags] | OTNO | XHOST
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | XHOST
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | ${dep}= | Set Variable | ${vte.dep_xhost}[0]
| | Call Method | ${sep.guest} | qemu_start
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${False}
| | Call Method | ${dep.guest} | qemu_start
| | Execute iperf Verification | ${verify_topology}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${True}
| | Call Method | ${dep.guest} | qemu_guest_poweroff

| virtio non-offload to non-offload XHOST
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
| | Execute iperf Verification | ${verify_topology}
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${True}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${True}
| | Call Method | ${dep.guest} | qemu_guest_poweroff

| virtio non-offload to offload XHOST
| | [Tags] | NOTO | XHOST
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | XHOST
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | ${dep}= | Set Variable | ${vte.dep_xhost}[0]
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${False}
| | Call Method | ${sep.guest} | qemu_start
| | Call Method | ${dep.guest} | qemu_start
| | Execute iperf Verification | ${verify_topology}
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${True}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | qemu_guest_poweroff

| virtio multiple queues offload to offload XHOST
| | [Tags] | MQ | OTO | XHOST
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | ${verify_topology}= | Run keyword
| | ...                 | Verify Topology Select Pair | ${verify_topology} | XHOST
| | ${vte}= | Get From List | ${verify_topology.allow} | 0
| | ${sep}= | Set Variable | ${vte.sep}
| | ${dep}= | Set Variable | ${vte.dep_xhost}[0]
| | Call Method | ${sep.guest} | reconfigure_vhost_user_if | ${sep.vif} | offload=${True} | qpair=${4}
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${True} | qpair=${4}
| | Call Method | ${sep.guest} | qemu_start
| | Call Method | ${dep.guest} | qemu_start
| | Execute iperf Verification | ${verify_topology} | parallel=${16}
| | Call Method | ${dep.guest} | verify_active_rxq | ${dep.vif}
| | Call Method | ${dep.guest} | reconfigure_vhost_user_if | ${dep.vif} | offload=${True} | qpair=${1}
| | Call Method | ${sep.guest} | qemu_guest_poweroff
| | Call Method | ${dep.guest} | qemu_guest_poweroff
