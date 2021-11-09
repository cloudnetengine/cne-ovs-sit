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
| Force Tags | BASIC | SMOKE
| Suite Setup | Run Keywords | Setup Uplink Bridge on All SUTs | br0
| ...         | AND          | Add VIF Ports on All SUTs | br0
| ...         | AND          | Start VMs on All SUTs
| Suite Teardown | Run Keywords | Stop VMs on All SUTs
| ...            | AND          | Teardown Uplink Bridge on All SUTs | br0
| Documentation | *Virtual Switch basic functions.*


*** Test Cases ***
| Simple icmp test
| | [Tags] | PING
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute Ping Verification | ${verify_topology}

| Simple iperf test
| | [Tags] | IPERF
| | ${verify_topology}= | Run keyword | Verify Topology Get
| | Execute iperf Verification | ${verify_topology}
