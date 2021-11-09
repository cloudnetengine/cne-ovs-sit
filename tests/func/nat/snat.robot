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
| Force Tags | NAT | SNAT
| Suite Setup | Run Keywords | Setup Uplink Bridge on All SUTs | br0
| ...         | AND          | Add VIF Ports on All SUTs | br0
| ...         | AND          | Start VMs on All SUTs
| ...         | AND          | Additional suite setup
| Suite Teardown | Run Keywords | Stop VMs on All SUTs
| ...            | AND          | Teardown Uplink Bridge on All SUTs | br0
| ...            | AND          | Additional suite teardown
| Documentation | *vSwitch SNAT function.*

*** Keywords ***
# Have to use a dedicated keyword for suite setup,
# as it doesn't support to populate a variable by a keyword returned value
| Additional suite setup
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Set suite variable | ${verify_topology}
| | SNAT Configure VMs | ${verify_topology}

| Additional suite teardown
| | NAT Restore VMs | ${verify_topology}

*** Test Cases ***
| SNAT telnet 1 IP 0 PORT 1 SERVER
| | [Tags] | TELNET
| | Verify SNAT | ${verify_topology} | 1 | 0 | 1 | telnet

| SNAT telnet 1 IP 2 PORT 2 SERVER
| | [Tags] | TELNET
| | Verify SNAT | ${verify_topology} | 1 | 2 | 2 | telnet

| SNAT telnet 1 IP 2 PORT 2 SERVER 2 PARALLEL
| | [Tags] | TELNET
| | Verify SNAT | ${verify_topology} | 1 | 2 | 2 | telnet | 2

| SNAT ping 1 IP 0 PORT 1 SERVER
| | [Tags] | PING
| | Verify SNAT | ${verify_topology} | 1 | 0 | 1 | ping

| SNAT ping 1 IP 2 PORT 2 SERVER
| | [Tags] | PING
| | Verify SNAT | ${verify_topology} | 1 | 2 | 2 | ping

| SNAT ping 1 IP 2 PORT 2 SERVER 2 PARALLEL
| | [Tags] | PING
| | Verify SNAT | ${verify_topology} | 1 | 2 | 2 | ping | 2

# unlike udp/tcp, icmp connections are not limited by port range
| SNAT ping 1 IP 2 PORT 2 SERVER 3 PARALLEL
| | [Tags] | PING
| | Verify SNAT | ${verify_topology} | 1 | 2 | 2 | ping | 3

| SNAT ping 3200 1 IP 0 PORT 1 SERVER
| | [Tags] | PING
| | Verify SNAT | ${verify_topology} | 1 | 0 | 1 | ping | 1 | 3200

| SNAT ping 3200 1 IP 2 PORT 2 SERVER
| | [Tags] | PING
| | Verify SNAT | ${verify_topology} | 1 | 2 | 2 | ping | 1 | 3200

| SNAT ping 3200 1 IP 2 PORT 2 SERVER 2 PARALLEL
| | [Tags] | PING
| | Verify SNAT | ${verify_topology} | 1 | 2 | 2 | ping | 2 | 3200

# unlike udp/tcp, icmp connections are not limited by port range
| SNAT ping 3200 1 IP 2 PORT 2 SERVER 3 PARALLEL
| | [Tags] | PING
| | Verify SNAT | ${verify_topology} | 1 | 2 | 2 | ping | 3 | 3200

| SNAT tftp 1 IP 0 PORT 1 SERVER
| | [Tags] | TFTP
| | Verify SNAT | ${verify_topology} | 1 | 0 | 1 | tftp

# unlike FTP active, TFTP cannot work with SNPAT
# because the data connection from TFTP server is sent to NPATed port,
# while TFTP client is actually not listen on that port
# conntrack-dump is as following:
# udp,orig=(src=172.170.100.1,dst=172.168.1.2,sport=34545,dport=69),reply=(src=172.168.1.2,dst=172.168.0.254,sport=69,dport=10002),zone=1
# udp,orig=(src=172.168.1.2,dst=172.168.0.254,sport=47203,dport=10002),reply=(src=172.170.100.1,dst=172.168.1.2,sport=10002,dport=47203),zone=1
#| SNAT tftp 1 IP 2 PORT 1 SERVER
#| | [Tags] | TFTP | PPP
#| | Verify SNAT | ${verify_topology} | 1 | 2 | 1 | tftp

| SNAT ftp passive 1 IP 0 PORT 1 SERVER
| | [Tags] | FTP_PASSIVE
| | Verify SNAT | ${verify_topology} | 1 | 0 | 1 | ftp_passive

# FTP passive works for SNPAT
| SNAT ftp_passive 1 IP 2 PORT 1 SERVER
| | [Tags] | FTP_PASSIVE
| | Verify SNAT | ${verify_topology} | 1 | 2 | 1 | ftp_passive

| SNAT ftp active 1 IP 0 PORT 1 SERVER
| | [Tags] | FTP_ACTIVE
| | Verify SNAT | ${verify_topology} | 1 | 0 | 1 | ftp_active

# for SNPAT, active FTP's data connection actually a DNAT from
# ftp server -> ftp client, and it's NOT a DNPAT
# following is a dump-conntrack result
# tcp,orig=(src=172.170.100.1,dst=172.168.1.2,sport=37258,dport=21),reply=(src=172.168.1.2,dst=172.168.0.254,sport=21,dport=10001),zone=1,protoinfo=(state=ESTABLISHED)
# tcp,orig=(src=172.168.1.2,dst=172.168.0.254,sport=20,dport=50977),reply=(src=172.170.100.1,dst=172.168.1.2,sport=50977,dport=20),zone=1,protoinfo=(state=FIN_WAIT_1)
#
| SNAT ftp_active 1 IP 2 PORT 1 SERVER
| | [Tags] | FTP_ACTIVE
| | Verify SNAT | ${verify_topology} | 1 | 2 | 1 | ftp_active

| SNAT related
| | [Tags] | RELATED
| | Verify SNAT Related | ${verify_topology}
