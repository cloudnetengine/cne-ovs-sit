#!/bin/bash -e

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
    autoconf libtool python numactl socat git screen gdb meson ninja-build

# Refer to https://docs.openvswitch.org/en/latest/faq/releases/
# for the DPDK version used in each OVS version.
declare -A branch_map
branch_map['branch-2.13']='19.11'
branch_map['branch-2.14']='19.11'
branch_map['branch-2.15']='20.11'
branch_map['branch-2.16']='20.11'

TEST_ROOT="$PWD/TEST_ROOT"
TEST_SRC_DIR="${TEST_ROOT}/src"
TEST_BIN_DIR="${TEST_ROOT}/bin"

#OVS_BRANCH="branch-2.13"
OVS_BRANCH="branch-2.16"
DPDK_BRANCH=${branch_map[$OVS_BRANCH]}
use_pkg_conf=true
if [ "$DPDK_BRANCH" == "19.11" ]; then
    use_pkg_conf=false
fi

DPDK_SRC_NAME="dpdk-stable"
DPDK_DIR="${TEST_SRC_DIR}/${DPDK_SRC_NAME}"
OVS_SRC_NAME="ovs"
OVS_DIR="${TEST_SRC_DIR}/${OVS_SRC_NAME}"

# The qemu version must be compatable with qemu agent inside VMs
QEMU_VERSION="5.2.0"
QEMU_NAME="qemu-${QEMU_VERSION}"
# 'QEMU_OUTPUT_DIR' is the location of qemu-system-x86_64,
# if it's not there, the dir needs to be updated.
QEMU_OUTPUT_DIR="${QEMU_NAME}/build"
QEMU_TARBALL="${QEMU_NAME}.tar.xz"
QEMU_URL="http://download.qemu.org/${QEMU_TARBALL}"

GDB_INIT="/root/.gdbinit"
if [ ! -f ${GDB_INIT} ]
then
    echo 'set pagination off ' | sudo tee ${GDB_INIT}
fi

mkdir -p ${TEST_SRC_DIR}
mkdir -p ${TEST_BIN_DIR}

# Build with release binaries by default
build_type="release"
if [ $# -eq 1 ]; then
    build_type=$1
elif [ $# -gt 1 ]; then
    echo "Too many parameters"
    exit
fi

# Need to initialize build for a fresh deployment or build type change.
initialize_build=false
if [ -f ${TEST_ROOT}/.build_type ]
then
    old_build_type=`cat ${TEST_ROOT}/.build_type`
    if [ "$build_type" != "$old_build_type" ]
    then
        initialize_build=true
    fi
else
    initialize_build=true
fi

dpdk_build_option=""
ovs_build_option=""
if [ $build_type = "debug" ]
then
    dpdk_build_option="-Dbuildtype=debug"
    ovs_build_option="-O0 -g"
else
    ovs_build_option=" -Ofast -msse4.2 -mpopcnt "
fi

cd ${TEST_SRC_DIR}
img_file="sit-buildroot/release-images/cne-ovs-sit-vm-1.0.img"
if [ ! -f ${img_file} ]
then
    # Download the CNE-OVS-SIT VM image.
    git clone https://github.com/cloudnetengine/sit-buildroot.git
    cp ${img_file} ${TEST_ROOT}
fi

# Download DPDK
if [ ! -d "$DPDK_DIR" ]
then
    git clone git://dpdk.org/dpdk-stable
fi
cd $DPDK_DIR
dpdk_branch_change=false
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "$DPDK_BRANCH" ]]; then
    dpdk_branch_change=true
    # Disard any uncommitted change
    git checkout .
    git checkout $DPDK_BRANCH
    cp "${DPDK_DIR}/usertools/dpdk-devbind.py" ${TEST_BIN_DIR}
fi

if $initialize_build || $dpdk_branch_change
then
    rm -rf $DPDK_DIR/build
fi

# Bulid DPDK
if $use_pkg_conf
then
    cd $DPDK_DIR
    export DPDK_BUILD="$DPDK_DIR/build"
    meson build ${dpdk_build_option}
    ninja -C build
    sudo ninja -C build install
    sudo ldconfig
    # Re-export DPDK_BUILD for passing 'static' to ovs configure
    export DPDK_BUILD="static"
else
    cd $DPDK_DIR
    # Don't compile any kernel module
    sed -i -r "s/(CONFIG_RTE_EAL_IGB_UIO *= *).*/\1n/" "config/common_linux"
    sed -i -r "s/(CONFIG_RTE_KNI_KMOD *= *).*/\1n/" "config/common_linux"
    sed -i -r "s/(CONFIG_RTE_LIBRTE_KNI *= *).*/\1n/" "config/common_linux"
    sed -i -r "s/(CONFIG_RTE_LIBRTE_PMD_KNI *= *).*/\1n/" "config/common_linux"
    make install T=x86_64-native-linuxapp-gcc -j4
    export DPDK_BUILD="${DPDK_DIR}/x86_64-native-linuxapp-gcc"
fi

cd ${TEST_SRC_DIR}
# Download OVS
if [ ! -d "$OVS_DIR" ]
then
    git clone https://github.com/openvswitch/ovs.git
fi

cd $OVS_DIR
ovs_branch_change=false
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "$OVS_BRANCH" ]]; then
    ovs_branch_change=true
    # Disard any uncommitted change
    git checkout .
    git checkout "${OVS_BRANCH}"
fi

if $initialize_build || $ovs_branch_change
then
    ./boot.sh
    ./configure --disable-ssl --with-dpdk=$DPDK_BUILD --with-logdir=/var/log/openvswitch --with-rundir=/var/run/openvswitch CFLAGS="${ovs_build_option}"
fi

# Build OVS
rm -rf ${OVS_DIR}/vswitchd/ovs-vswitchd
make -j4
OVS_BIN_DIR="${TEST_BIN_DIR}/openvswitch"
rm -rf ${OVS_BIN_DIR}
rm -rf "${TEST_BIN_DIR}/ovs-native"
rm -rf "${TEST_BIN_DIR}/ovs-dpdk"
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

# Download and build QEMU
cd ${TEST_SRC_DIR}
# Download QEMU
if [ ! -f "${TEST_SRC_DIR}/${QEMU_TARBALL}" ]
then
    wget ${QEMU_URL} --no-check-certificate
fi
qemu_bin="${TEST_SRC_DIR}/${QEMU_OUTPUT_DIR}/qemu-system-x86_64"
if [ ! -f ${qemu_bin} ]
    then
    tar xJf ${QEMU_TARBALL}
    cd ${TEST_SRC_DIR}/${QEMU_NAME}
    ./configure --target-list=x86_64-softmmu --disable-linux-aio --disable-curses --disable-sdl --disable-gtk --disable-vte --disable-cocoa
    make -j4
    rm -rf "${TEST_BIN_DIR}/qemu"
    ln -s ${TEST_SRC_DIR}/${QEMU_OUTPUT_DIR} "${TEST_BIN_DIR}/qemu"
fi

echo $build_type > ${TEST_ROOT}/.build_type
