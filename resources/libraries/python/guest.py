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

"""Library for executing commands in guest."""

from io import StringIO
import re
from ipaddress import IPv4Address, IPv6Address
from robot.api import logger
from resources.libraries.python.ssh import exec_cmd, kill_process, SSHTimeout

__all__ = [
    u"Guest",
]

def _ip_is_v4(ip_addr):
    if isinstance(ip_addr, IPv4Address):
        ipv4 = True
    elif isinstance(ip_addr, IPv6Address):
        ipv4 = False
    else:
        raise RuntimeError(f"Invalid ip address: {ip_addr}")
    return ipv4

def _verify_ping_result(log, exp_cnt):
    # summary format '2 packets transmitted, 2 received, 0% packet loss, time 1001ms'
    regex = re.compile(r'\s+(\d+)\s+packets transmitted')
    match = regex.search(log)
    if not match:
        logger.warn("ping test has no summary")
        return False

    sent = int(match.group(1))
    regex = re.compile(r'\s+(\d+)\s+received')
    match = regex.search(log)
    recv = int(match.group(1))
    logger.debug('sent:{0} recv:{1} exp_cnt:{2}'.format(sent, recv, exp_cnt))
    if sent != exp_cnt:
        logger.warn('sent:{0} is not equal to expected:{1}'.format(sent, exp_cnt))
        return False
    if recv < exp_cnt:
        logger.warn(f"recv:{recv} is less than expected:{exp_cnt}")
        return False
    return True

def _verify_iperf_result(log, exp_rate=0):
    # $ iperf3 -6 -c 2001:1000:1000:1000::aca8:101 -f k
    # ...
    # [ ID] Interval           Transfer     Bandwidth       Retr  Cwnd
    # [  4]   0.00-1.00   sec  1.13 GBytes  9693816 Kbits/sec  443    534 KBytes
    # [  4]   1.00-2.00   sec  1.61 GBytes  13804173 Kbits/sec  678    757 KBytes
    # [  4]   2.00-3.00   sec  1.34 GBytes  11488700 Kbits/sec  622    512 KBytes
    # [  4]   3.00-4.00   sec  1.66 GBytes  14240768 Kbits/sec  818    524 KBytes
    # [  4]   4.00-5.00   sec  1.65 GBytes  14211005 Kbits/sec  684    558 KBytes
    # [  4]   5.00-6.00   sec  1.64 GBytes  14082017 Kbits/sec  411    548 KBytes
    # [  4]   6.00-7.00   sec  1.65 GBytes  14165441 Kbits/sec  720    545 KBytes
    # [  4]   7.00-8.00   sec  1.66 GBytes  14245942 Kbits/sec  901    541 KBytes
    # [  4]   8.00-9.00   sec  1.55 GBytes  13340002 Kbits/sec  562    735 KBytes
    # [  4]   9.00-10.00  sec  1.68 GBytes  14443332 Kbits/sec  722    782 KBytes
    # [  4]   9.00-10.00  sec  0.00 GBytes      0.00 Kbits/sec  722    782 KBytes
    # - - - - - - - - - - - - - - - - - - - - - - - - -
    # [ ID] Interval           Transfer     Bandwidth       Retr
    # [  4]   0.00-10.00  sec  15.6 GBytes  13371471 Kbits/sec  6561             sender
    # [  4]   0.00-10.00  sec  15.6 GBytes  13369569 Kbits/sec                  receiver
    buf = StringIO(log)
    results = list()
    regex = re.compile(r'\s+(\d+\.*\d+)\s+Kbits\/sec')
    for line in buf.readlines():
        #logger.debug('line :{0}'.format(line))
        match = regex.search(line)
        if match:
            results.append(match.group(1))
            #logger.debug('Bandwidth:{0}'.format(match.group(1)))
    buf.close()
    if len(results) == 0:
        logger.warn('NO Bandwidth output')
        return "0 Kbits/sec"
    first_one = True
    bw = 0
    zero_cnt = 0
    for result in results:
        bw = float(result)
        if bw == 0:
            zero_cnt = zero_cnt + 1
            logger.warn('zero Bandwidth accumulated count:{0}'.format(zero_cnt))
            if zero_cnt > 5:
                logger.warn('zero Bandwidth exceed threshold')
                return (False, -1)
        if exp_rate > 0 and not first_one: # don't check the 1st second
            if abs(bw - exp_rate) > (exp_rate / 10):
                logger.warn('invalid Bandwidth:{0} exp_rate:{1}'.format(
                    bw, exp_rate))
                return (False, -1)
        if first_one:
            first_one = False
    return f"{int(bw)} Kbits/sec"

def _verify_iperf_udp_result(log, exp_rate=0):
    # $ sudo iperf3 -c 172.168.2.1 -u -l 63k -b 10G
    # Connecting to host 172.168.2.1, port 5201
    # [  4] local 172.168.1.1 port 56551 connected to 172.168.2.1 port 5201
    # [ ID] Interval           Transfer     Bandwidth       Total Datagrams
    # [  4]   0.00-1.00   sec  40.7 MBytes   342 Mbits/sec  662
    # [  4]   1.00-2.00   sec  57.3 MBytes   481 Mbits/sec  932
    # [  4]   2.00-3.00   sec  46.0 MBytes   386 Mbits/sec  748
    # [  4]   3.00-4.00   sec  60.2 MBytes   505 Mbits/sec  978
    # [  4]   4.00-5.00   sec  54.0 MBytes   453 Mbits/sec  877
    # [  4]   5.00-6.00   sec  53.9 MBytes   452 Mbits/sec  876
    # [  4]   6.00-7.00   sec  48.4 MBytes   406 Mbits/sec  787
    # [  4]   7.00-8.00   sec  57.2 MBytes   480 Mbits/sec  930
    # [  4]   8.00-9.00   sec  43.1 MBytes   361 Mbits/sec  700
    # [  4]   9.00-10.00  sec  34.5 MBytes   289 Mbits/sec  560
    # - - - - - - - - - - - - - - - - - - - - - - - - -
    # [ ID] Interval           Transfer     Bandwidth       Jitter    Lost/Total Datagrams
    # [  4]   0.00-10.00  sec   495 MBytes   415 Mbits/sec  43.480 ms  7768/8002 (97%)
    # [  4] Sent 8002 datagrams

    # we don't count on 'Bandwidth' which is miss-leading in udp case,
    # we use Lost/Total counters instead.
    buf = StringIO(log)
    sign_found = False
    re_sign = re.compile(r'Jitter')
    re_sum = re.compile(r'\s+(\d+)\/(\d+)\s+')
    lost = 0
    total = 0
    #regex = re.compile(r'\s+(\d+\.*\d+)\s+Kbits\/sec')
    for line in buf.readlines():
        logger.debug('line :{0}'.format(line))
        if sign_found:
            s = re_sum.search(line)
            if not s:
                return 0
            lost = int(s.group(1))
            total = int(s.group(2))
            break

        match = re_sign.search(line)
        if match:
            sign_found = True
            logger.debug('summary found')
    buf.close()

    # we used to think udp summary will show up even deny is in place
    # but looks like the session cannot be setup thus timeout
    logger.debug('Lost/Total: {0}/{1}'.format(lost, total))
    # we assume iperf udp is using 63k/10seconds to test
    if lost == total:
        return 0

    # we don't count eth/ip/ipv6/udp header overhead
    # as they are trivial comparing to 63k
    rate = float((total - lost) * 63 * 1024) / 10.0 * 8 / 1000 # in kbps

    if exp_rate != 0 and abs(rate - exp_rate) > (exp_rate / 10):
        logger.warn(f"invalid Bandwidth:{rate} exp_rate:{exp_rate}")
    return f"{int(rate)} Kbits/sec"

def _process_netperf_result(stdout, testname='TCP_RR'):
    buf = StringIO(stdout)
    regex = re.compile(r"(\d+)[ ]+(\d+)[ ]+(\d+)[ ]+(\d+)[ ]+(\d+(?:\.\d+)?)[ ]+(\d+(?:\.\d+)?)")
    for line in buf.readlines():
        match = regex.search(line)
        if match:
            logger.debug("Find the line {}".format(line))
            return match.group(6)
    logger.warn(f"{testname} doesn't have valid result.")
    return 0

class Guest():
    """Contains methods for executing guest commands. """

    def __init__(self, name):
        self.name = name
        self.vifs = list()
        self._ssh_info = {}
        self._host_ssh_info = {}

    def kill_process(self, proc_name):
        """Kill a process in the guest.

        :param proc_name: Process name to be killed.
        :type proc_name: str
        """
        kill_process(self._ssh_info, proc_name)

    def execute(self, cmd, timeout=30, sudo=True, exp_fail=False):
        """Execute a command in the guest.

        :param cmd: Command to be executed.
        :param timeout: Timeout value in seconds. Defualt: 30
        :param sudo: Sudo privilege execution flag. Default: False.
        :param exp_fail: Expect the command failure or success. Default: False.
                         None means don't care about the command result.
        :type cmd: str
        :type timeout: int
        :type sudo: bool
        :type exp_fail: bool
        :returns: RC, Stdout, Stderr.
        :rtype: tuple(int, str, str)
        """
        # If the command is supposed to fail, it might be relatively long
        # to wait for its timeout, so forcibly use 30 seconds to speed up a little.
        if exp_fail:
            timeout = 30

        try:
            ret_code, stdout, stderr = \
                exec_cmd(self._ssh_info, f"{cmd}", timeout, sudo)
            logger.trace(stdout)
        except SSHTimeout: # THere might be timeout in 'exp_fail' case
            ret_code = -1
            stdout = ''
            stderr = ''

        if ret_code is None or int(ret_code) != 0:
            # 'None' for exp_fail means don't care the result
            if exp_fail is not None and not exp_fail:
                logger.error(f"Execute cmd failed on {self.name} : {cmd}")
            # Normalize return code as -1
            ret_code = -1
        else:
            if exp_fail:
                logger.error(f"Execute cmd should fail on {self.name} : {cmd}")

        return (ret_code, stdout, stderr)

    def execute_batch(self, cmds):
        """Execute a batch of commands in the guest.

        :param cmds: Commands to be executed.
        :type cmds: list(str)
        """
        for cmd in cmds:
            self.execute(cmd)

    def execute_host(self, cmd, timeout=30):
        """Execute a command on a host which the guest resides.

        :param cmd: Command.
        :param timeout: Timeout value in seconds.
        :type cmd: str
        :type timeout: int
        :returns: ret_code, stdout, stderr
        :rtype: tuple(int, str, str)
        """
        ret_code, stdout, stderr = \
            exec_cmd(self._host_ssh_info, cmd, timeout, sudo=True)
        logger.trace(stdout)

        if ret_code is None or int(ret_code) != 0:
            raise RuntimeError(f"Execute host cmd failed on "
                               f"{self._host_ssh_info['host']} : {cmd}")

        return (ret_code, stdout, stderr)

    def execute_host_batch(self, cmds, timeout=30):
        """Execute a batch of commands on a host which the guest resides.

        :param cmds: Commands.
        :param timeout: Timeout value in seconds.
        :type cmds: list(str)
        :type timeout: int
        """
        for cmd in cmds:
            self.execute_host(cmd, timeout)

    def add_vif(self, vif):
        """Add a VIF to the guest.

        :param vif: Virtual interface to be added.
        :type vif: VirtualInterface obj
        """
        self.vifs.append(vif)

    def configure_interface(self):
        """Configure network addresses inside the guest according to VIFs' spec.
        """
        self.execute("ip addr list")
        for vif in self.vifs:
            ipv4_str = vif.if_addr.ipv4_str_with_prefix()
            ipv6_str = vif.if_addr.ipv6_str_with_prefix()

            cmds = [f"ip -4 addr add {ipv4_str} dev virtio{vif.idx}",
                    f"ip -6 addr add {ipv6_str} dev virtio{vif.idx}",
                    f"ip link set virtio{vif.idx} up"]
            self.execute_batch(cmds)
            if vif.qpair > 1:
                # start from 'combined 2' otherwise 'ethtool -L' will complain with
                # 'combined unmodified, ignoring'
                for q_idx in range(2, vif.qpair + 1):
                    self.execute(f"ethtool -L virtio{vif.idx} combined {q_idx}")

    def configure_mtu(self, mtu):
        """Configure mtu of network interfaces inside the guest.

        :param mtu: Requested MTU.
        :type mtu: int
        """
        for vif in self.vifs:
            self.execute(f"ip link set virtio{vif.idx} mtu {mtu}")

    def configure(self):
        """Configure a guest after it starts.
        """
        self.configure_interface()

    def _exec_ping(self, cmd, cnt, exp_fail):
        _, stdout, _ = self.execute(cmd, exp_fail=exp_fail)
        if not exp_fail:
            _verify_ping_result(stdout, cnt)


    def ping_ipv4_addr(self, ipv4, cnt=5, exp_fail=False):
        """Ping an ipv4 address from the guest.

        :param ipv4: Destination ipv4 address.
        :param cnt: Number of packets to send. Default: 5
        :param exp_fail: Expect the command failure or success. Default: False.
                         None means don't care about the command result.
        :type ipv4: IPv4Address obj
        :type cnt: int
        :type exp_fail: bool
        """
        for cmd in [f"ping -c {cnt} -i 0.3 {ipv4}",
                    f"ping -c {cnt} -i 0.3 -s 1600 {ipv4}",
                    f"ping -c {cnt} -i 0.3 -s 3200 {ipv4}"]:
            self._exec_ping(cmd, cnt, exp_fail)

    def ping_ipv6_addr(self, ipv6, cnt=5, exp_fail=False):
        """Ping an ipv6 address from the guest.

        :param ipv6: Destination ipv6 address.
        :param cnt: Number of packets to send. Default: 5
        :param exp_fail: Expect the command failure or success. Default: False.
                         None means don't care about the command result.
        :type ipv4: IPv6Address obj
        :type cnt: int
        :type exp_fail: bool
        """
        for cmd in [f"ping -6 -c {cnt} -i 0.3 {ipv6}",
                    f"ping -6 -c {cnt} -i 0.3 -s 1600 {ipv6}",
                    f"ping -6 -c {cnt} -i 0.3 -s 3200 {ipv6}"]:
            self._exec_ping(cmd, cnt, exp_fail)

    def start_netperf_server(self, ipv4=True):
        """Run netperf server in the guest.

        :param ipv4: Run in v4 mode.
        :type ipv4: bool
        """
        if ipv4:
            options = ''
        else:
            options = '-6'
        self.execute(f"netserver {options}")

    def stop_netperf_server(self):
        """Stop netperf server in the guest. """
        kill_process(self._ssh_info, "netserver")

    def _run_netperf_client(self, server_ip, testname='TCP_RR'):
        cmd = f"netperf -H {server_ip} -l 10 -t {testname}"
        ret_code, stdout, _ = self.execute(cmd)
        logger.debug("netperf result: {}".format(stdout))
        if ret_code != 0:
            return (False, -1)
        r_string = _process_netperf_result(stdout, testname)
        return (True, r_string)

    def execute_netperf_ipv4(self, server_vm, server_ip, testname='TCP_RR'):
        """Execute netperf ipv4 test.
        Only test TCP_RR for now.

        :param server_vm: Destination guest to run netperf server.
        :param server_ip: Destination ipv4 address.
        :param testname: Netperf test type.
        :type server_vm: Guest obj
        :type server_ip: IPv4Address obj
        :type testname: str
        :returns: Test result.
        :rtype: str
        """
        server_vm.start_netperf_server(ipv4=True)
        (succ, r_string) = self._run_netperf_client(server_ip, testname)
        server_vm.stop_netperf_server()
        if not succ:
            raise RuntimeError("NetPerf Not Successful")
        return f"TCP_RR ipv4 {r_string} Tran/sec"

    def execute_netperf_ipv6(self, server_vm, server_ip, testname='TCP_RR'):
        """Execute netperf ipv6 test.
        Only test TCP_RR for now.

        :param server_vm: Destination guest to run netperf server.
        :param server_ip: Destination ipv6 address.
        :param testname: Netperf test type.
        :type server_vm: Guest obj
        :type server_ip: IPv6Address obj
        :type testname: str
        :returns: Test result.
        :rtype: str
        """
        server_vm.start_netperf_server(ipv4=False)
        (succ, r_string) = self._run_netperf_client(server_ip, testname)
        server_vm.stop_netperf_server()
        if not succ:
            raise RuntimeError("NetPerf Not Successful")
        return f"TCP_RR ipv6 {r_string} Tran/sec"

    def start_iperf_server(self, ipv4=True):
        """Run iperf server in the guest.

        :param ipv4: Run in v4 mode.
        :type ipv4: bool
        """
        if ipv4:
            options = ''
        else:
            options = '-6'
        self.execute(f"iperf3 {options} -s -D")

    def stop_iperf_server(self):
        """Stop netperf server in the guest. """
        kill_process(self._ssh_info, "iperf3")

    def _run_iperf_client(self, server_ip, bw=0, proto='tcp',
                          parallel=1, exp_fail=False):
        if _ip_is_v4(server_ip):
            options = ''
        else:
            options = '-6'

        if bw:
            options += f" -b {bw}K "

        if proto == 'udp':
            udp_options = '-u -l 63k'
        else:
            udp_options = ''

        if parallel > 1:
            parallel_options = f"-P {parallel}"
        else:
            parallel_options = ''

        cmd = f"iperf3 {options} -c {server_ip} -t 10 -f k " \
              f"{udp_options} {parallel_options}"
        _, stdout, _ = self.execute(cmd, 50, exp_fail=exp_fail)

        rate = 0
        if not exp_fail:
            if proto == 'udp':
                rate = _verify_iperf_udp_result(stdout, rate)
            else:
                rate = _verify_iperf_result(stdout, rate)
        return rate

    def execute_iperf_ipv4(self, server_vm, server_ip, bw=0, proto='tcp',
                           parallel=1, exp_fail=False):
        """Execute iperf ipv4 test.

        :param server_vm: Destination guest to run iperf server.
        :param server_ip: Destination ipv4 address.
        :param bw: Bandwidth in kbps. Default: 0 means unlimited
        :param proto: Test protocol. Default: "tcp"
        :param parallel: Number of concurrent streams. Default: 1
        :param exp_fail: Expect the command failure or success. Default: False.
                         None means don't care about the command result.
        :type server_vm: Guest obj
        :type server_ip: IPv4Address obj
        :type bw: int
        :type proto: str
        :type parallel: int
        :type exp_fail: bool
        :returns: Test result in kbps.
        :rtype: str
        """
        server_vm.start_iperf_server(ipv4=True)
        rate = self._run_iperf_client(server_ip, bw, proto, parallel, exp_fail)
        server_vm.stop_iperf_server()
        return f"{proto} ipv4 throughput: {rate}"

    def execute_iperf_ipv6(self, server_vm, server_ip, bw=0, proto='tcp',
                           parallel=1, exp_fail=False):
        """Execute iperf ipv6 test.

        :param server_vm: Destination guest to run iperf server.
        :param server_ip: Destination ipv6 address.
        :param bw: Bandwidth in kbps. Default: 0 means unlimited
        :param proto: Test protocol. Default: "tcp"
        :param parallel: Number of concurrent streams. Default: 1
        :param exp_fail: Expect the command failure or success. Default: False.
                         None means don't care about the command result.
        :type server_vm: Guest obj
        :type server_ip: IPv6Address obj
        :type bw: int
        :type proto: str
        :type parallel: int
        :type exp_fail: bool
        :returns: Test result in kbps.
        :rtype: str
        """
        server_vm.start_iperf_server(ipv4=False)
        rate = self._run_iperf_client(server_ip, bw, proto, parallel, exp_fail)
        server_vm.stop_iperf_server()
        return f"{proto} ipv6 throughput: {rate}"

    # The test VM as very limited space on test vm, thus using 1MB test file
    def _generate_file(self, fname):
        cmd = f"dd if=/dev/urandom of=./{fname} bs=1k count=1k"
        self.execute(cmd)

    def rm_file(self, fname):
        """Delete a file in a guest.

        :param fname: File name.
        :type fname: str
        """
        cmd = f"rm {fname}"
        self.execute(cmd)

    def _compare_files(self, file1, file2):
        cmd = f"diff {file1} {file2}"
        (_, stdout, stderr) = self.execute(cmd)
        if stdout or stderr:
            logger.error('test files are not identical')

    def execute_tftp(self, server_vm, server_ip):
        """Execute tftp test.
        TFTP server is already started during VM init process,
        here only used for deleting test file.

        :param server_vm: Destination guest to run tftp server.
        :param server_ip: Destination ipv6 address.
        :type server_vm: Guest obj
        :type server_ip: IPv4Address or IPv6Address obj
        """
        fname = "tfile"
        self._generate_file(fname)
        cmds = [f"tftp {server_ip} -c put {fname} {fname}_remote",
                f"tftp {server_ip} -c get {fname}_remote {fname}_local"]
        self.execute_batch(cmds)
        self._compare_files(f"{fname}", f"{fname}_local")
        self.rm_file(f"{fname}")
        self.rm_file(f"{fname}_local")
        # Note tftp doesn't have 'delete' command.
        # tftpd file directory is under 'tmp' according to vm image patch.
        server_vm.rm_file(f"/tmp/{fname}_remote")

    def execute_ftp(self, server_vm, server_ip, active):
        """Execute tftp test.
        FTP server is already started during VM init process,
        here only used for deleting test file.

        :param server_vm: Destination guest to run tftp server.
        :param server_ip: Destination ipv6 address.
        :param active: Using ftp active or passive mode
        :type server_vm: Guest obj
        :type server_ip: IPv4Address or IPv6Address obj
        :type active: bool
        """
        ipv4 = _ip_is_v4(server_ip)
        base_cmd = 'sudo curl '
        if active:
            base_cmd += '--ftp-port - '
            if ipv4:
                # vswitch doesn't support EPRT in ipv4 right now
                base_cmd += '--disable-eprt '
        else:
            base_cmd += '--ftp-pasv '
            if ipv4:
                # vswitch doesn't support EPSV in ipv4 right now
                base_cmd += '--disable-epsv '

        base_cmd += 'ftp://'
        if ipv4:
            base_cmd += f"{server_ip}"
        else:
            base_cmd += f"[{server_ip}]"

        fname = "tfile"
        self._generate_file(fname)
        cmds = [f"{base_cmd}/{fname}_remote --user \"cne:cne\" -T ./{fname} " \
                    f"--ftp-create-dirs",
                f"{base_cmd}/{fname}_remote --user \"cne:cne\" -o ./{fname}_local " \
                        f"--ftp-create-dirs"]
        self.execute_batch(cmds)
        self._compare_files(f"{fname}", f"{fname}_local")
        self.rm_file(f"{fname}")
        self.rm_file(f"{fname}_local")
        server_vm.rm_file(f"/tmp/{fname}_remote")
