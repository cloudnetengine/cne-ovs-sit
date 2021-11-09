# CNE-OVS-SIT - OVS System Integration Test Suite

1. [Introduction](#introduction)
1. [User guide](#user-guide)
1. [Discussion](#discussion)

## Introduction

CNE-OVS-SIT is a test suite for OVS end-to-end function and performance tests,
and mainly focus on userspace datapath, i.e. OVS-DPDK.

The suite covers a variety of datapath functions: VLAN, tunnels, conntrack, NAT,
bond, multiple queues, and offloading etc. It also includes interoperability
tests between OVS-DPDK and OVS kernel datapath. The performance metrics currently
supported are throughput and RTT under customizable configurations.

The suite requires two SUT (System Under Test) nodes which run virtual switches
and virtual machines, and one MGMT node runs the suite to conduct
the tests. The end-to-end workloads are running inside VMs which are
built by buildroot, and the workloads could be iperf, netperf, tftp, ftp etc.

A typical work flow is as following:
- Giving a topology file which specifies SUT config, e.g. uplink interfaces,
  hugepage, login info etc,.
- Specify test cases to run (or not run) by their tags.
- The suite then creates network components such as bridges/ports, setup flows,
  spawn virtual machines, then configures VMs' networks.
- The suite selects endpoint pairs (VIF A to VIF B) which represent typical
  virtual topologies and run workloads to verify the results.

## User guide

[Quick start](docs/quick_start.rst) documentaion is
describing how to run the suite.

[Advanced guide](docs/advanced_guide.rst) documentaion is
describing more details about suite execution.

## Discussion

For any question, please open issues of the repository or send requests
to info@cloudnetengine.com.
