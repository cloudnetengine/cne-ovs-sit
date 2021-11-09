Advanced Topics
-------------------------------

Directory structure
=====================

The suite has two layers:

   - Top layer is using robot to write all the test cases,
     and all the cases are under "tests/" directory.

   - Bottom layer is using python modules to implement low-level logics,
     and all the modules are under "resources/libraries/python/" directory.

Please refer to the source code for details.

Test case selection
=====================

CNE-OVS-SIT test cases are organized by robotframework, so you can easily
customize the test cases you want to run. For example:

   - If you only want to run preformance test, change command in tox.ini to::

        robot -L TRACE -v TOPOLOGY_PATH:topologies/enabled/my.yaml --include PERF tests/

   - If you only want to run VXLAN preformance test, change command in tox.ini to::

        robot -L TRACE -v TOPOLOGY_PATH:topologies/enabled/my.yaml --include VXLANANDPERF tests/

For more details, refer to "Tag patterns" from `robot framework document
<https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html>`_.

Virtual Machine Specification
=====================

The suite tries to create 2 VMs per NUMA node on each SUT node,
and there might be less than 2 VMs on a particular NUMA node in case resource is not enough.
A VM's memory and vcpu are always colocated on a single NUMA node.

   - Memory
       A VM uses 1GB memory by default, "vm_mem_size" in MB of SUT spec can override the default.

   - CPU
       A VM uses 1 core by default, "vm_cpu_num" of SUT spec can override the default.

   - Network
        Each VM has 3 VNICs, one for management, and the other two are used for test.

Virtual Switch CPU affinity (Only apply to OVS-DPDK)
=====================

The suite allocates 1 core to vswitch on each numa node.

   - "pnic_numa_cpu_num" and "norm_numa_cpu_num" of SUT spec can be used to
     override the default number.

NOTE: core 0 is always reserved for SUT system service, i.e. virtual switch and VMs
are never running on core 0.

Uplink parameters
======================================

Uplink interface parameters can be customized.

   - "n_queue_pair"
   - "n_rxq_desc"
   - "n_txq_desc"

Interoperability test
======================================

The config yaml can be specified with "dp-type" as "ovs-dpdk" and "ovs-native"
respectively for the two SUT nodes, and this can test the interoperability
between the two type of vswitches.

NFV workload test
======================================

Currently the suite doesn't support NFV workload test, you can refer to `vswitchperf
<https://github.com/opnfv/vswitchperf.git>`_.

Debugging
==============================

There might be some cases that needs to debug ovs, the suite provide an
option to attach a gdb session to ovs-vswitchd process. You can do following
steps to debug ovs-vswitchd.

   - Provide "-v ATTACH_GDB:True" option to robot command, e.g.::

        $ robot -L TRACE -v ATTACH_GDB:True -v TOPOLOGY_PATH:topologies/enabled/my.yaml --include SMOKE tests/

   - On SUT node, gdb session can be attached by::

        $ screen -r gdbscreen
