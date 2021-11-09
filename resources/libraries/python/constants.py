# Copyright(c) 2017-2021 CloudNetEngine. All rights reserved.

# Copyright (c) 2016 Cisco and/or its affiliates.
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

"""Library for constants."""

class Constants():
    """Contains constants definitions."""

    VNI_NONE = 0
    OFP_LOCAL = 0
    OFP_UPLINK_BASE = 1
    OFP_VHOST_BASE = 10
    OFP_TUNNEL_BASE = 100

    OF_TABLE_ADMISS = 0
    OF_TABLE_INPUT = 20
    OF_TABLE_ACL = 30
    OF_TABLE_CORE = 40
    OF_TABLE_FIB = 50
    OF_TABLE_NAT = 60
    OF_TABLE_L2_MATCH = 70
    OF_TABLE_OUTPUT = 80
