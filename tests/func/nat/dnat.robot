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
| Library | resources.libraries.python.nat
| Library | resources.libraries.python.conntrack
| Library | resources.libraries.python.topology
| Force Tags | NAT | DNAT
| Suite Setup | Run Keywords | Setup Uplink Bridge on All SUTs | br0
| ...         | AND          | Add VIF Ports on All SUTs | br0
| ...         | AND          | Start VMs on All SUTs
| ...         | AND          | Additional suite setup
| Suite Teardown | Run Keywords | Stop VMs on All SUTs
| ...            | AND          | Teardown Uplink Bridge on All SUTs | br0
| ...            | AND          | Additional suite teardown
| Documentation | *vSwitch DNAT function.*


*** Keywords ***
| Additional suite setup
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Set suite variable | ${verify_topology}
| | DNAT Configure VMs | ${verify_topology}

| Additional suite teardown
| | NAT Restore VMs | ${verify_topology}

*** Test Cases ***
| DNAT telnet 1 IP 0 PORT 1 SERVER
| | [Tags] | TELNET
| | Verify DNAT | ${verify_topology} | telnet

| DNAT ping 1 IP 0 PORT 1 SERVER
| | [Tags] | PING
| | Verify DNAT | ${verify_topology} | ping

| DNAT ping 3200 1 IP 0 PORT 1 SERVER
| | [Tags] | PING
| | Verify DNAT | ${verify_topology} | ping | 3200

| DNAT tftp 1 IP 0 PORT 1 SERVER
| | [Tags] | TFTP
| | Verify DNAT | ${verify_topology} | tftp

| DNAT ftp passive 1 IP 0 PORT 1 SERVER
| | [Tags] | FTP_PASSIVE
| | Verify DNAT | ${verify_topology} | ftp_passive

| DNAT ftp active 1 IP 0 PORT 1 SERVER
| | [Tags] | FTP_ACTIVE
| | Verify DNAT | ${verify_topology} | ftp_active

| SNAT related
| | [Tags] | RELATED
| | Verify DNAT Related | ${verify_topology}
