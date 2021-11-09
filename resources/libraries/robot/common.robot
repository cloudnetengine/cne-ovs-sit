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

*** Keywords ***
| Print Results
| | [Documentation] | Print test results on screen
| | [Arguments] | ${results}
| | ${output}= | Set Variable | ${EMPTY}
| | :FOR | ${r} | IN | @{results}
| | | ${output}= | Catenate | ${output} | ${\n}${SPACE}${SPACE}${SPACE}${SPACE}${r}
| | log to console | ${output}
