Running CNE-OVS-SIT in ubuntu-20.04
-------------------------------

Setup management node
=====================

Download the suite and install dependency packages::

   $ git clone https://github.com/cloudnetengine/cne-ovs-sit.git
   $ sudo apt-get install -y build-essential tox python3-dev

Setup SUT node
======================================

1. Make SUT login user sudo passwordless:

   Add the following line to /etc/sudoers with root privilege::

      username	ALL=(ALL) NOPASSWD: ALL
         where: ``username`` is the user name used to login the SUT

2. Configure hugepages:

   Customize GRUB_CMDLINE_LINUX_DEFAULT option in /etc/default/grub:

       - hugepage config, e.g. using 1G hugepages:
         "default_hugepagesz=1GB hugepagesz=1G hugepages=N"
           where: ``N`` is number of huge pages requested

       - isolcpus option to isolate cores from the Linux scheduler,
         so the performance result is more stable.

   $ sudo update-grub2

   $ sudo reboot #After the reboot, make sure hugetlbfs is mounted on /dev/hugepages.

3. Install packages::

   Copy bootstrap-ubuntu.sh to SUT nodes and run the script under $HOME dir.

Run tests
==============================

1. Customize config for your test environment:

   - Copy topologies/enabled/sample_normal.yaml to topologies/enabled/my.yaml

   - Customize 'host', 'username', 'password', 'pci_address' etc. in my.yaml
     based on your own setup.

   - You can create a new testenv named 'my_env' section in tox.ini to use your own config, e.g.::

        [testenv:my_env]
        basepython=python3.8
        deps = -r{toxinidir}/requirements.txt
        setenv = PYTHONPATH=.
        commands =
            robot -L TRACE -v TOPOLOGY_PATH:topologies/enabled/my.yaml --include SMOKE tests/

2. Launch the suite for a smoking test (The first time tox execution needs more
   time to install dependency packages)::

   $ cd cne-ovs-sit
   $ tox -e my_env
   Note: 'my_env' is created above in tox.ini.
