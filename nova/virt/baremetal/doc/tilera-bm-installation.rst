
Packages
=====

* This procedure is for RHEL. Reading 'tilera-bm-instance-creation.txt' may make this document easy to understand.

* TFTP, NFS, EXPECT, and Telnet installation::

  $ yum install nfs-utils.x86_64 expect.x86_64 tftp-server.x86_64 telnet

* TFTP configuration::

    $ cat /etc/xinetd.d/tftp
    # default: off
    # description: The tftp server serves files using the trivial file transfer \
    #       protocol.  The tftp protocol is often used to boot diskless \
    #       workstations, download configuration files to network-aware printers,
    #       \
    #       and to start the installation process for some operating systems.
    service tftp
    {
          socket_type             = dgram
          protocol                = udp
          wait                    = yes
          user                    = root
          server                  = /usr/sbin/in.tftpd
          server_args             = -s /tftpboot
          disable                 = no
          per_source              = 11
          cps                     = 100 2
          flags                   = IPv4
    }
    $ /etc/init.d/xinetd restart

* NFS configuration::

    $ mkdir /tftpboot
    $ mkdir /tftpboot/fs_x (x: the id of tilera board)
    $ cat /etc/exports
    /tftpboot/fs_0 tilera0-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    /tftpboot/fs_1 tilera1-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    /tftpboot/fs_2 tilera2-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    /tftpboot/fs_3 tilera3-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    /tftpboot/fs_4 tilera4-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    /tftpboot/fs_5 tilera5-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    /tftpboot/fs_6 tilera6-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    /tftpboot/fs_7 tilera7-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    /tftpboot/fs_8 tilera8-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    /tftpboot/fs_9 tilera9-eth0(sync,rw,no_root_squash,no_all_squash,no_subtree_check)
    $ sudo /etc/init.d/nfs restart
    $ sudo /usr/sbin/exportfs

* TileraMDE install: TileraMDE-3.0.1.125620::

  $ cd /usr/local/
  $ tar -xvf tileramde-3.0.1.125620_tilepro.tar
  $ tar -xjvf tileramde-3.0.1.125620_tilepro_apps.tar.bz2
  $ tar -xjvf tileramde-3.0.1.125620_tilepro_src.tar.bz2
  $ mkdir /usr/local/TileraMDE-3.0.1.125620/tilepro/tile
  $ cd /usr/local/TileraMDE-3.0.1.125620/tilepro/tile/
  $ tar -xjvf tileramde-3.0.1.125620_tilepro_tile.tar.bz2
  $ ln -s /usr/local/TileraMDE-3.0.1.125620/tilepro/ /usr/local/TileraMDE

* Installation for 32-bit libraries to execute TileraMDE::

  $ yum install glibc.i686 glibc-devel.i686



Nova Directories
======

::

	$ sudo mkdir /var/lib/nova/baremetal
	$ sudo mkdir /var/lib/nova/baremetal/console



Nova Flags
=====

Set these flags in nova.conf::

	# baremetal database connection
	# (The database will be created in the next section)
	baremetal_sql_connection = mysql://$ID:$Password@127.0.0.1/nova_bm

	# baremetal compute driver
	compute_driver = nova.virt.baremetal.driver.BareMetalDriver
	baremetal_driver = nova.virt.baremetal.tilera.TILERA
	power_manager = nova.virt.baremetal.tilera_pdu.Pdu

	# instance_type_extra_specs this baremetal compute
	instance_type_extra_specs = cpu_arch:tilepro64

	# TFTP root
	baremetal_tftp_root = /tftpboot

	# baremetal scheduler host manager
	scheduler_host_manager = nova.scheduler.baremetal_host_manager.BaremetalHostManager



Baremetal Database
=====

Create the baremetal database. Grant all provileges to the user specified by the 'baremetal_sql_connection' flag.

Example::

	$ mysql -p
	mysql> create database nova_bm;
	mysql> grant all privileges on nova_bm.* to '$ID'@'%' identified by '$Password';
	mysql> exit

Create tables::

	$ nova-bm-manage db sync



Create Tilera Baremetal Instance Type
=====

First, create a tilera instance type in the normal way.

Example::

	$ nova-manage instance_type create --name=tp64.8x8 --cpu=64 --memory=16218 --root_gb=917 --ephemeral_gb=0 --flavor=6 --swap=1024 --rxtx_factor=1
	(about --flavor, see 'How to choose the value for flavor' section below)

Next, set baremetal extra_spec to the instance type::

	$ nova-manage instance_type set_key --name=tp64.8x8 --key cpu_arch --value 's== tilepro64'


How to choose the value for flavor.
-----

Run nova-manage instance_type list, find the maximum FlavorID in output. Use the maximum FlavorID+1 for new instance_type::

	$ nova-manage instance_type list
	m1.medium: Memory: 4096MB, VCPUS: 2, Root: 40GB, Ephemeral: 0Gb, FlavorID: 3, Swap: 0MB, RXTX Factor: 1.0, ExtraSpecs {}
	m1.small: Memory: 2048MB, VCPUS: 1, Root: 20GB, Ephemeral: 0Gb, FlavorID: 2, Swap: 0MB, RXTX Factor: 1.0, ExtraSpecs {}
	m1.large: Memory: 8192MB, VCPUS: 4, Root: 80GB, Ephemeral: 0Gb, FlavorID: 4, Swap: 0MB, RXTX Factor: 1.0, ExtraSpecs {}
	m1.tiny: Memory: 512MB, VCPUS: 1, Root: 0GB, Ephemeral: 0Gb, FlavorID: 1, Swap: 0MB, RXTX Factor: 1.0, ExtraSpecs {}
	m1.xlarge: Memory: 16384MB, VCPUS: 8, Root: 160GB, Ephemeral: 0Gb, FlavorID: 5, Swap: 0MB, RXTX Factor: 1.0, ExtraSpecs {}

In the example above, the maximum Flavor ID is 5, so use 6.



Start Processes
======

::

	(Currently, you might have trouble if run processes as a user other than the superuser...)
	$ sudo nova-scheduler &
	$ sudo nova-compute &



Register Baremetal Host and NIC
=====

First, register a baremetal node. Next, register the baremetal node's NICs.

To register a baremetal node, use 'nova-bm-manage node create'.
It takes the parameters listed below.

* --host: baremetal nova-compute's hostname
* --cpus: number of cores
* --memory_mb: memory size in MegaBytes
* --local_gb: local disk size in GigaBytes
* --pm_address: tilera node's static IP address
* --pm_user: username
* --pm_password: password
* --prov_mac_address: tilera node's MAC address
* --terminal_port: TCP port for ShellInABox. Each node must use unique TCP port. If you do not need console access, use 0.

Example::

	$ nova-bm-manage node create --service_host=bm1 --cpus=64 --memory_mb=16218 --local_gb=917 --pm_address=10.0.2.1 --pm_user=test --pm_password=password --prov_mac_address=98:4b:e1:67:9a:4c --terminal_port=0

To verify the node registration, run 'nova-bm-manage node list'::

	$ nova-bm-manage node list
	ID        SERVICE_HOST  INSTANCE_ID   CPUS    Memory    Disk      PM_Address        PM_User           TERMINAL_PORT  PROV_MAC            PROV_VLAN
	1         bm1           None          64      16218     917       10.0.2.1          test              0   98:4b:e1:67:9a:4c   None

To register NIC, use 'nova-bm-manage interface create'.
It takes the parameters listed below.

* --node_id: ID of the baremetal node owns this NIC (the first column of 'nova-bm-manage node list')
* --mac_address: this NIC's MAC address in the form of xx:xx:xx:xx:xx:xx
* --datapath_id: datapath ID of OpenFlow switch this NIC is connected to
* --port_no: OpenFlow port number this NIC is connected to

(--datapath_id and --port_no are used for network isolation. It is OK to put 0, if you do not have OpenFlow switch.)

Example::

	$ nova-bm-manage interface create --node_id=1 --mac_address=98:4b:e1:67:9a:4e --datapath_id=0 --port_no=0

To verify the NIC registration, run 'nova-bm-manage interface list'::

	$ nova-bm-manage interface list
	ID        BM_NODE_ID        MAC_ADDRESS         DATAPATH_ID       PORT_NO
	1         1                 98:4b:e1:67:9a:4e   0x0               0



Run Instance
=======

Run instance using the baremetal instance type.
Make sure to use kernel and image that support baremetal hardware (i.e contain drivers for baremetal hardware ).

Example::

	euca-run-instances -t tp64.8x8 -k my.key ami-CCC
