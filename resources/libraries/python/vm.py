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

"""QEMU utilities library."""

from time import time, sleep
import json
import os
import re
from io import StringIO

from robot.api import logger

from resources.libraries.python.guest import Guest
from resources.libraries.python.ssh import SSHTimeout

__all__ = [
    u"VirtualMachine",
]

class VirtualMachine(Guest):
    """QEMU utilities."""

    VM_MEM_SIZE = 1024 #MB
    VM_VIFS_NUM = 2
    VM_CPU_NUM = 1

    # QEMU Machine Protocol socket
    __QMP_SOCK = '/tmp/qmp.sock'
    # QEMU Guest Agent socket
    __QGA_SOCK = '/tmp/qga.sock'


    def __init__(self, name, vm_idx, vm_mem_size, vm_host_cpus, huge_mnt,
                 host_ssh_info, test_root_dir, ovs_native=False):
        super().__init__(name)

        self._qmp_sock = '{0}{1}'.format(self.__QMP_SOCK, vm_idx)
        self._qga_sock = '{0}{1}'.format(self.__QGA_SOCK, vm_idx)
        self.host_cpus = vm_host_cpus

        self._qemu_opt = {}
        # Default 1 CPU.
        self._qemu_opt['smp'] = '-smp {0},sockets={0},cores=1,threads=1'.format(
            len(self.host_cpus))
        # Daemonize the QEMU process after initialization. Default one
        # management interface.
        self._qemu_opt['options'] = '-cpu host -daemonize -enable-kvm ' \
            '-machine pc-i440fx-2.8,accel=kvm,usb=off,mem-merge=off ' \
            '-net nic,model=virtio '
        self._qemu_opt['ssh_fwd_port'] = 10022 + vm_idx
        # Default serial console port
        self._qemu_opt['serial_port'] = 4556 + vm_idx
        self._qemu_opt['vnc_port'] = vm_idx
        # Default 512MB virtual RAM
        self._qemu_opt['mem_size'] = vm_mem_size/1024 #MB
        # Default huge page mount point, required for Vhost-user interfaces.
        self._qemu_opt['huge_mnt'] = huge_mnt
        # Default do not allocate huge pages.
        self._qemu_opt['huge_allocate'] = True
        # Default image for CSIT virl setup
        self._qemu_opt['disk_image'] = '/tmp/vm.img.{0}'.format(vm_idx)
        # VM node info dict
        self._host_ssh_info = host_ssh_info
        self._ssh_info = {
            'host': self._host_ssh_info['host'],
            'port': self._qemu_opt['ssh_fwd_port'],
            'username': 'cne',
            'password': 'cne',
        }
        self._vhost_id = 0
        self.numa_id = 0
        self._ssh = None
        self._socks = [self._qmp_sock, self._qga_sock]
        self._is_ovs_native = ovs_native
        self._vhost_net_pids = []

        self.qemu_bin = os.path.join(test_root_dir,
                                     'bin/qemu/qemu-system-x86_64')
        # Change img file if needed.
        self.img_base = os.path.join(test_root_dir, 'cne-ovs-sit-vm-1.0.img')

        self.execute_host(f"cp {self.img_base} {self._qemu_opt.get('disk_image')}")


    def qemu_set_ssh_fwd_port(self, fwd_port):
        """Set host port for guest SSH forwarding.

        :param fwd_port: Port number on host for guest SSH forwarding.
        :type fwd_port: int
        """
        self._qemu_opt['ssh_fwd_port'] = fwd_port
        self._ssh_info['port'] = fwd_port

    def qemu_set_serial_port(self, port):
        """Set serial console port.

        :param port: Serial console port.
        :type port: int
        """
        self._qemu_opt['serial_port'] = port

    def qemu_set_mem_size(self, mem_size):
        """Set virtual RAM size.

        :param mem_size: RAM size in Mega Bytes.
        :type mem_size: int
        """
        self._qemu_opt['mem_size'] = int(mem_size)

    def qemu_set_huge_mnt(self, huge_mnt):
        """Set hugefile mount point.

        :param huge_mnt: System hugefile mount point.
        :type huge_mnt: int
        """
        self._qemu_opt['huge_mnt'] = huge_mnt

    def qemu_set_huge_allocate(self):
        """Set flag to allocate more huge pages if needed."""
        self._qemu_opt['huge_allocate'] = True

    def qemu_set_disk_image(self, disk_image):
        """Set disk image.

        :param disk_image: Path of the disk image.
        :type disk_image: str
        """
        self._qemu_opt['disk_image'] = disk_image

    def qemu_set_affinity(self):
        """Set qemu affinity by getting thread PIDs via QMP and taskset to list
        of CPU cores.

        :param host_cpus: List of CPU cores.
        :type host_cpus: list
        """
        qemu_cpus = self._qemu_qmp_exec('query-cpus')['return']

        if len(qemu_cpus) != len(self.host_cpus):
            logger.debug('Host CPU count {0}, Qemu Thread count {1}'.format(
                len(self.host_cpus), len(qemu_cpus)))
            raise ValueError('Host CPU count must match Qemu Thread count')

        for qemu_cpu, host_cpu in zip(qemu_cpus, self.host_cpus):
            cmd = 'taskset -p {0} {1}'.format(hex(1 << int(host_cpu)),
                                              qemu_cpu['thread_id'])
            (ret_code, _, stderr) = self.execute_host(cmd)
            if int(ret_code) != 0:
                logger.debug('Set affinity failed {0}'.format(stderr))
                raise RuntimeError('Set affinity failed on {0}'.format(
                    self._host_ssh_info['host']))

    def _qemu_generate_vhost_user_if_option(self, vif):
        """Add Vhost-user interface.

        :param socket: Path of the unix socket.
        :param server: If True the socket shall be a listening socket.
        :param mac: Vhost-user interface MAC address (optional, otherwise is
            used autogenerated MAC 52:54:00:00:04:xx).
        :type socket: str
        :type server: bool
        :type mac: str
        """

        netdev_mq_option = ''
        device_mq_option = ''
        device_ol_option = ''
        if int(vif.qpair) > 1:
            netdev_mq_option = ',queues={0}'.format(vif.qpair)
            device_mq_option = ',mq=on,vectors={0}'.format(int(vif.qpair) * 2 + 2)
        if not vif.offload:
            device_ol_option = ',csum=off,gso=off,guest_tso4=off,guest_tso6=off,'\
                'guest_ecn=off'

        if not self._is_ovs_native:
            # Create unix socket character device.
            chardev = f" -chardev socket,id=vhuchar{vif.idx},path={vif.sock}"
            if vif.backend_client_mode is True:
                chardev += ',server'
            vif.qemu_option += chardev

            # Create Vhost-user network backend.
            netdev = ' -netdev vhost-user,id=vhost{0},chardev=vhuchar{0}{1}'.format(
                vif.idx, netdev_mq_option)
            vif.qemu_option += netdev
        else:
            netdev = ' -netdev tap,id=vhost{0},vhost=on,ifname={1},' \
                     'script={2},downscript={3}'.format(
                         vif.idx, vif.name, vif.qemu_script_ifup, vif.qemu_script_ifdown)
            vif.qemu_option = netdev

        # Create Virtio network device.
        # set mrg_rxbuf for trex performance concern
        device = ' -device virtio-net-pci,netdev=vhost{0},mac={1}{2}{3}'.format(
            vif.idx, vif.mac, device_ol_option, device_mq_option)
        vif.qemu_option += device

    def add_vhost_user_if(self, vif):
        """Add a vhost user interface.

        :param vif: Virtual interface.
        :type vif: VhostUserInterface obj
        """
        super().add_vif(vif)
        self._qemu_generate_vhost_user_if_option(vif)

    # Reconfigure vif doens't impact vif's index on a VM.
    def reconfigure_vhost_user_if(self, vif, offload=True, qpair=1):
        """Reconfigure attributes of a vhost user interface.

        :param vif: Virtual interface.
        :param offload: Enable offload or not.
        :param qpair: Number of rx/tx queue pairs.
        :type vif: VhostUserInterface obj
        :type offload: bool
        :type qpair: int
        """
        vif.qemu_option = ''
        vif.offload = offload
        vif.qpair = qpair
        self._qemu_generate_vhost_user_if_option(vif)

    def _qemu_qmp_exec(self, cmd):
        """Execute QMP command.

        QMP is JSON based protocol which allows to control QEMU instance.

        :param cmd: QMP command to execute.
        :type cmd: str
        :return: Command output in python representation of JSON format. The
            { "return": {} } response is QMP's success response. An error
            response will contain the "error" keyword instead of "return".
        """
        # To enter command mode, the qmp_capabilities command must be issued.
        qmp_cmd = 'echo "{ \\"execute\\": \\"qmp_capabilities\\" }' + \
            '{ \\"execute\\": \\"' + cmd + '\\" }" | sudo -S socat - UNIX-CONNECT:' + \
            self._qmp_sock
        (ret_code, stdout, stderr) = self.execute_host(qmp_cmd)
        if int(ret_code) != 0:
            logger.debug('QMP execute failed {0}'.format(stderr))
            raise RuntimeError('QMP execute "{0}"'
                               ' failed on {1}'.format(cmd, self._host_ssh_info['host']))
        logger.trace(stdout)
        # Skip capabilities negotiation messages.
        out_list = stdout.splitlines()
        if len(out_list) < 3:
            raise RuntimeError('Invalid QMP output on {0}'.format(
                self._host_ssh_info['host']))
        return json.loads(out_list[2])

    def _qemu_qga_flush(self):
        """Flush the QGA parser state
        """
        qga_cmd = 'printf "\xFF" | sudo -S nc ' \
            '-q 1 -U ' + self._qga_sock
        logger.console(f"+++++++++++ {qga_cmd}")
        (ret_code, stdout, stderr) = self._ssh.exec_command(qga_cmd)
        if int(ret_code) != 0:
            logger.warn('----- QGA execute failed {0}'.format(stderr))
            raise RuntimeError('QGA execute "{0}" '
                               'failed on {1}'.format(qga_cmd, self._host_ssh_info['host']))
        logger.warn(f"111111 {stdout}")
        if not stdout:
            return {}
        lines = stdout.split('\n', 1)
        ret_line = lines[-1]
        logger.warn(f"22222 [{lines}]")
        logger.warn(f"33333 [{ret_line}]")
        return json.loads(stdout.split('\n', 1)[-1])

    def _qemu_qga_exec(self, cmd, timeout=100):
        """Execute QGA command.

        QGA provide access to a system-level agent via standard QMP commands.

        :param cmd: QGA command to execute.
        :type cmd: str
        """
        #qga_cmd = 'echo "{ \\"execute\\": \\"' + cmd + '\\" }" | sudo -S nc ' \
        #    '-q 1 -U ' + self._qga_sock
        qga_cmd = '(echo "{ \\"execute\\": \\"' + cmd + '\\" }"; sleep 1) | sudo -S socat ' \
                ' - UNIX-CONNECT:' + self._qga_sock
        (ret_code, stdout, stderr) = self._ssh.exec_command(qga_cmd, timeout)
        if int(ret_code) != 0:
            logger.debug('QGA execute failed {0}'.format(stderr))
            raise RuntimeError('QGA execute "{0}"'
                               ' failed on {1}'.format(cmd, self._host_ssh_info['host']))
        logger.trace(stdout)
        if not stdout:
            return {}
        return json.loads(stdout.split('\n', 1)[0])

    def _wait_until_vm_boot(self, timeout=300):
        """Wait until QEMU VM is booted.

        Ping QEMU guest agent each 5s until VM booted or timeout.

        :param timeout: Waiting timeout in seconds (optional, default 300s).
        :type timeout: int
        """
        start = time()
        while 1:
            if time() - start > timeout:
                raise RuntimeError('timeout, VM {0} not booted on {1}'.format(
                    self._qemu_opt['disk_image'], self._host_ssh_info['host']))

            try:
                rc, _, _ = self.execute("pwd", timeout=5, exp_fail=None)
            except (SSHTimeout, IOError):
                rc = -1

            if int(rc) != 0:
                logger.debug(f"guest is not booted yet.")
                sleep(5)
                continue

            break

        logger.trace('VM {0} booted on {1}'.format(self._qemu_opt['disk_image'],
                                                   self._host_ssh_info['host']))

    def qemu_start(self):
        """Start QEMU and wait until VM boot.

        :return: VM node info.
        :rtype: dict
        .. note:: First set at least node to run QEMU on.
        .. warning:: Starts only one VM on the node.
        """
        # SSH forwarding
        ssh_fwd = '-net user,hostfwd=tcp::{0}-:22'.format(
            self._qemu_opt.get('ssh_fwd_port'))
        # Memory and huge pages
        mem = '-object memory-backend-file,id=mem,size={0}M,mem-path={1},' \
            'share=on -m {0} -numa node,memdev=mem'.format(
                self._qemu_opt.get('mem_size'), self._qemu_opt.get('huge_mnt'))

        # Setup QMP via unix socket
        qmp = '-qmp unix:{0},server,nowait'.format(self._qmp_sock)
        # Setup serial console
        serial = '-chardev socket,host=127.0.0.1,port={0},id=gnc0,server,' \
            'nowait -device isa-serial,chardev=gnc0'.format(
                self._qemu_opt.get('serial_port'))
        # Setup QGA via chardev (unix socket) and isa-serial channel
        qga = '-chardev socket,path={0},server,nowait,id=qga0 ' \
            '-device isa-serial,chardev=qga0'.format(self._qga_sock)
        # Graphic setup
        #graphic = '-monitor none -display none -vga none'
        graphic = '-monitor none -display none -vnc :{0}'.format(self._qemu_opt['vnc_port'])

        # Run QEMU
        vif_options = ''
        for vif in self.vifs:
            vif_options += vif.qemu_option

        cmd = f"{self.qemu_bin} {self._qemu_opt.get('smp')} {mem} {ssh_fwd} " \
              f"{self._qemu_opt.get('options')} {vif_options} " \
              f"-hda {self._qemu_opt.get('disk_image')} {qmp} {serial} {qga} {graphic}"
        # Add numactl
        cmd = 'numactl --cpunodebind {0} --membind {0} '.format(self.numa_id) + cmd
        self.execute_host(cmd, timeout=300)
        logger.trace('QEMU running')
        # Wait until VM boot
        self._wait_until_vm_boot()

        self.qemu_set_affinity()
        self.configure()

    def qemu_quit(self):
        """Quit the QEMU emulator."""
        out = self._qemu_qmp_exec('quit')
        err = out.get('error')
        if err is not None:
            raise RuntimeError('QEMU quit failed on {0}, error: {1}'.format(
                self._host_ssh_info['host'], json.dumps(err)))

    def qemu_system_powerdown(self):
        """Power down the system (if supported)."""
        out = self._qemu_qmp_exec('system_powerdown')
        err = out.get('error')
        if err is not None:
            raise RuntimeError(
                'QEMU system powerdown failed on {0}, '
                'error: {1}'.format(self._host_ssh_info['host'], json.dumps(err))
            )

    def qemu_guest_poweroff(self):
        """Poweroff the system."""
        self.execute("poweroff")
        sleep(2)

        self.qemu_clear_socks()

    def qemu_system_reset(self):
        """Reset the system."""
        out = self._qemu_qmp_exec('system_reset')
        err = out.get('error')
        if err is not None:
            raise RuntimeError(
                'QEMU system reset failed on {0}, '
                'error: {1}'.format(self._host_ssh_info['host'], json.dumps(err)))

    def qemu_clear_socks(self):
        """Remove all sockets created by QEMU."""
        # If serial console port still open kill process
        cmd = 'fuser -k {}/tcp'.format(self._qemu_opt.get('serial_port'))
        self.execute_host(cmd)
        # Delete all created sockets
        for sock in self._socks:
            cmd = 'rm -f {}'.format(sock)
            self.execute_host(cmd)

    def qemu_cleanup(self):
        """Remove all resource associated with QEMU."""
        self._host_ssh_info['host_cpus'].extend(self.host_cpus)
        self.qemu_clear_socks()
        cmd = 'rm -f {}'.format(self._qemu_opt['disk_image'])
        for pid in self._vhost_net_pids:
            self._host_ssh_info['vhost_net_pids'].remove(pid)
        self.execute_host(cmd)
        self._ssh.disconnect(self._host_ssh_info)

    def verify_active_rxq(self, vif):
        """Verify traffic is distributed among vif's multiple queues.

        # Note device name in /proc/interrupts might not be the nic name,
        # and nic name is just an aliase which links to the real name, as following:
        # $ readlink /sys/class/net/virtio0
        # ../../devices/pci0000:00/0000:00:04.0/virtio1/net/virtio0
        # The device name is actually "virtio1".

        :param vif: Virtual interface.
        :type vif: VirtualInterface obj
        """
        cmd = f"readlink /sys/class/net/virtio{vif.idx}"
        _, stdout, _ = self.execute(cmd)
        path = os.path.split(stdout)
        for _ in range(2):
            path = os.path.split(path[0])
        dev_name = path[1]

        cmd = f"cat /proc/interrupts |grep {dev_name} |grep input"
        ret_code, stdout, _ = self.execute(cmd)
        if int(ret_code) != 0:
            logger.warn(f"{cmd} failed")
        # '/proc/interrupts' format:
        # 25:     615027   PCI-MSI 49153-edge      virtio0-input.0
        # 26:          1   PCI-MSI 49154-edge      virtio0-output.0
        # 27:     605792   PCI-MSI 49155-edge      virtio0-input.1
        # 28:          1   PCI-MSI 49156-edge      virtio0-output.1
        # 29:     619541   PCI-MSI 49157-edge      virtio0-input.2
        # 30:          1   PCI-MSI 49158-edge      virtio0-output.2
        # 31:     636156   PCI-MSI 49159-edge      virtio0-input.3
        # 32:          1   PCI-MSI 49160-edge      virtio0-output.3
        active_q = 0
        buf = StringIO(stdout)
        for line in buf.readlines():
            regex = re.compile(r'(\d+)\s+PCI')
            match = regex.search(line)
            interrupts = int(match.group(1))
            # at least 100 interrupts
            if interrupts > 100:
                active_q += 1
        buf.close()
        if active_q < vif.qpair:
            logger.error(f"active_q:{active_q} configured queue:{vif.qpair}")
