#!/bin/sh -e

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

sudo apt-get install -y --fix-missing build-essential pkg-config \
    libglib2.0-dev libfdt-dev libpixman-1-dev zlib1g-dev libnuma-dev \
    autoconf libtool python numactl socat git screen gdb

TEST_ROOT="$PWD/TEST_ROOT"
TEST_SRC_DIR="${TEST_ROOT}/src"
TEST_BIN_DIR="${TEST_ROOT}/bin"
OVS_VERSION="2.13.4"
DPDK_VERSION="19.11.8"
# The qemu version must be compatable with qemu agent inside VMs
QEMU_VERSION="2.5.0"
OVS_NAME="openvswitch-${OVS_VERSION}"
DPDK_NAME="dpdk-stable-${DPDK_VERSION}"
QEMU_NAME="qemu-${QEMU_VERSION}"
OVS_TARBALL="${OVS_NAME}.tar.gz"
DPDK_TARBALL="dpdk-${DPDK_VERSION}.tar.xz"
QEMU_TARBALL="${QEMU_NAME}.tar.xz"
OVS_URL="https://www.openvswitch.org/releases/${OVS_TARBALL}"
DPDK_URL="http://static.dpdk.org/rel/${DPDK_TARBALL}"
QEMU_URL="http://download.qemu.org/${QEMU_TARBALL}"

mkdir -p ${TEST_SRC_DIR}
mkdir -p ${TEST_BIN_DIR}

cd ${TEST_SRC_DIR}
img_file="sit-buildroot/release-images/cne-ovs-sit-vm-1.0.img"
if [ ! -f ${img_file} ]
then
    # Download the CNE-OVS-SIT VM image.
    git clone https://github.com/cloudnetengine/sit-buildroot.git
    cp ${img_file} ${TEST_ROOT}
fi

# Download DPDK and build it without kernel modules.
dpdk_lib="${TEST_SRC_DIR}/${DPDK_NAME}/x86_64-native-linuxapp-gcc/lib/libdpdk.a"
if [ ! -f ${dpdk_lib} ]
then
    wget ${DPDK_URL} --no-check-certificate
    tar xJf ${DPDK_TARBALL}
    cd ${TEST_SRC_DIR}/${DPDK_NAME}
    # Don't compile any kernel module
    sed -i -r "s/(CONFIG_RTE_EAL_IGB_UIO *= *).*/\1n/" "config/common_linux"
    sed -i -r "s/(CONFIG_RTE_KNI_KMOD *= *).*/\1n/" "config/common_linux"
    sed -i -r "s/(CONFIG_RTE_LIBRTE_KNI *= *).*/\1n/" "config/common_linux"
    sed -i -r "s/(CONFIG_RTE_LIBRTE_PMD_KNI *= *).*/\1n/" "config/common_linux"
    make install T=x86_64-native-linuxapp-gcc -j4
    cp "${TEST_SRC_DIR}/${DPDK_NAME}/usertools/dpdk-devbind.py" ${TEST_BIN_DIR}
fi

# Download OVS and build with DPDK support.
ovs_bin="${TEST_SRC_DIR}/${OVS_NAME}/vswitchd/ovs-vswitchd"
if [ ! -f ${ovs_bin} ]
then
    cd ${TEST_SRC_DIR}
    wget ${OVS_URL} --no-check-certificate
    tar zxf ${OVS_TARBALL}
    cd ${TEST_SRC_DIR}/${OVS_NAME}
    ./boot.sh
    export DPDK_BUILD=${TEST_SRC_DIR}/${DPDK_NAME}/x86_64-native-linuxapp-gcc
    ./configure --disable-ssl --with-dpdk=$DPDK_BUILD --with-logdir=/var/log/openvswitch --with-rundir=/var/run/openvswitch
    make -j4
    OVS_BIN_DIR=${TEST_BIN_DIR}/${OVS_NAME}
    mkdir -p ${OVS_BIN_DIR}
    cp ./utilities/ovs-dpctl ${OVS_BIN_DIR}
    cp ./utilities/ovs-appctl ${OVS_BIN_DIR}
    cp ./utilities/ovs-ofctl ${OVS_BIN_DIR}
    cp ./utilities/ovs-vsctl ${OVS_BIN_DIR}
    cp ./vswitchd/ovs-vswitchd ${OVS_BIN_DIR}
    cp ./ovsdb/ovsdb-server ${OVS_BIN_DIR}
    cp ./vswitchd/vswitch.ovsschema ${OVS_BIN_DIR}
    cp ./ovsdb/ovsdb-tool ${OVS_BIN_DIR}
    # OVS binaries can be shared by both userspace and kernel datapath.
    ln -s ${OVS_BIN_DIR} "${TEST_BIN_DIR}/ovs-native"
    ln -s ${OVS_BIN_DIR} "${TEST_BIN_DIR}/ovs-dpdk"
fi

# Download and build QEMU
qemu_bin="${TEST_SRC_DIR}/${QEMU_NAME}/x86_64-softmmu/qemu-system-x86_64"
if [ ! -f ${qemu_bin} ]
    then
    cd ${TEST_SRC_DIR}
    wget ${QEMU_URL} --no-check-certificate
    tar xJf ${QEMU_TARBALL}
    cd ${TEST_SRC_DIR}/${QEMU_NAME}
    ./configure --target-list=x86_64-softmmu --disable-linux-aio --disable-curses --disable-sdl --disable-gtk --disable-vte --disable-cocoa
    sed -i 's/\<memfd_create\>/tmp_memfd_create/g' util/memfd.c
    sed -i '/mntent\.h/ a\#include <sys/sysmacros.h>' qga/commands-posix.c
    make -j4
    ln -s ${TEST_SRC_DIR}/${QEMU_NAME} "${TEST_BIN_DIR}/qemu"
fi
