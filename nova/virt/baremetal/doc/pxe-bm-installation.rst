
Packages
=====

* This procedure is for Ubuntu 12.04 x86_64. Reading 'pxe-bm-instance-creation.txt' may make this document easy to understand.

* dnsmasq (PXE server for baremetal hosts)
* syslinux (bootloader for PXE)
* ipmitool (operate IPMI)
* qemu-kvm (only for qemu-img)
* open-iscsi (connect to iSCSI target at berametal hosts)
* busybox (used in deployment ramdisk)
* tgt (used in deployment ramdisk)

Example::

	$ sudo apt-get install dnsmasq syslinux ipmitool qemu-kvm open-iscsi
	$ sudo apt-get install busybox tgt


Ramdisk for Deployment
=====

To create a deployment ramdisk, use 'baremetal-mkinitrd.sh' in [baremetal-initrd-builder](https://github.com/NTTdocomo-openstack/baremetal-initrd-builder)::

	$ cd baremetal-initrd-builder
	$ ./baremetal-mkinitrd.sh <ramdisk output path> <kernel version>

Modules in /lib/<kernel version>/modules are used to create ramdisk.
You can specify a 'generic' kernel installed to the working host.

Example::

	$ ./baremetal-mkinitrd.sh /tmp/deploy-ramdisk.img 3.2.0-26-generic
	working in /tmp/baremetal-mkinitrd.9AciX98N
	368017 blocks


Register the kernel and the ramdisk to Glance.

Example::

	$ glance add name="baremetal deployment ramdisk" is_public=true container_format=ari disk_format=ari < /tmp/deploy-ramdisk.img
	Uploading image 'baremetal deployment ramdisk'
	===========================================[100%] 114.951697M/s, ETA  0h  0m  0s
	Added new image with ID: e99775cb-f78d-401e-9d14-acd86e2f36e3

	$ glance add name="baremetal deployment kernel" is_public=true container_format=aki disk_format=aki < /boot/vmlinuz-3.2.0-26-generic
	Uploading image 'baremetal deployment kernel'
	===========================================[100%] 46.9M/s, ETA  0h  0m  0s
	Added new image with ID: d76012fc-4055-485c-a978-f748679b89a9


ShellInABox
=====
Baremetal nova-compute uses [ShellInABox](http://code.google.com/p/shellinabox/) so that users can access baremetal host's console through web browsers.

Build from source and install::

	$ sudo apt-get install gcc make
	$ tar xzf shellinabox-2.14.tar.gz
	$ cd shellinabox-2.14
	$ ./configure
	$ sudo make install


PXE Boot Server
=====

Prepare TFTP root directory::

	$ sudo mkdir /tftpboot
	$ sudo cp /usr/lib/syslinux/pxelinux.0 /tftpboot/
	$ sudo mkdir /tftpboot/pxelinux.cfg

Start dnsmasq.
Example: start dnsmasq on eth1 with PXE and TFTP enabled::

	$ sudo dnsmasq --conf-file= --port=0 --enable-tftp --tftp-root=/tftpboot --dhcp-boot=pxelinux.0 --bind-interfaces --pid-file=/dnsmasq.pid --interface=eth1 --dhcp-range=192.168.175.100,192.168.175.254

	(You may need to stop and disable dnsmasq)
	$ sudo /etc/init.d/dnsmasq stop
	$ sudo sudo update-rc.d dnsmasq disable


Nova Directories
======

::

	$ sudo mkdir /var/lib/nova/baremetal
	$ sudo mkdir /var/lib/nova/baremetal/console
	$ sudo mkdir /var/lib/nova/baremetal/dnsmasq


Nova Flags
=====

Set these flags in nova.conf::

	# baremetal database connection
	# (The database will be created in the next section)
	baremetal_sql_connection = mysql://nova_bm:password@127.0.0.1/nova_bm

	# baremetal compute driver
	compute_driver = nova.virt.baremetal.driver.BareMetalDriver
	baremetal_driver = nova.virt.baremetal.pxe.PXE
	power_manager = nova.virt.baremetal.ipmi.Ipmi

	# instance_type_extra_specs this baremetal compute
	instance_type_extra_specs = cpu_arch:x86_64

	# TFTP root
	baremetal_tftp_root = /tftpboot

	# path to shellinaboxd
	baremetal_term = /usr/local/bin/shellinaboxd

	# deployment kernel & ramdisk image id
	baremetal_deploy_kernel = d76012fc-4055-485c-a978-f748679b89a9
	baremetal_deploy_ramdisk = e99775cb-f78d-401e-9d14-acd86e2f36e3

	# baremetal scheduler host manager
	scheduler_host_manager = nova.scheduler.baremetal_host_manager.BaremetalHostManager


Baremetal Database
=====

Create the baremetal database. Grant all provileges to the user specified by the 'baremetal_sql_connection' flag.
Example::

	$ mysql -p
	mysql> create database nova_bm;
	mysql> grant all privileges on nova_bm.* to 'nova_bm'@'%' identified by 'password';
	mysql> exit

Create tables::

	$ nova-bm-manage db sync


Create Baremetal Instance Type
=====

First, create an instance type in the normal way.

Example::

	$ nova-manage instance_type create --name=bm.small --cpu=2 --memory=4096 --root_gb=10 --ephemeral_gb=20 --flavor=6 --swap=1024 --rxtx_factor=1
	(about --flavor, see 'How to choose the value for flavor' section below)

Next, set baremetal extra_spec to the instance type::

	$ nova-manage instance_type set_key --name=bm.small --key cpu_arch --value 'x86_64'

How to choose the value for flavor.
-----

Run nova-manage instance_type list, find the maximum FlavorID in output. Use the maximum FlavorID+1 for new instance_type.

::

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
	$ sudo bm_deploy_server &
	$ sudo nova-scheduler &
	$ sudo nova-compute &


Register Baremetal Host and NIC
=====

First, register a baremetal node. In this step, one of the NICs must be specified as a PXE NIC.
Ensure the NIC is PXE-enabled and the NIC is selected as a primary boot device in BIOS.

Next, register all the NICs except the PXE NIC specified in the first step.

To register a baremetal node, use 'nova-bm-manage node create'.
It takes the parameters listed below.

* --host: baremetal nova-compute's hostname
* --cpus: number of CPU cores
* --memory_mb: memory size in MegaBytes
* --local_gb: local disk size in GigaBytes
* --pm_address: IPMI address
* --pm_user: IPMI username
* --pm_password: IPMI password
* --prov_mac_address: PXE NIC's MAC address
* --terminal_port: TCP port for ShellInABox. Each node must use unique TCP port. If you do not need console access, use 0.

Example::

	$ nova-bm-manage node create --host=bm1 --cpus=4 --memory_mb=6144 --local_gb=64 --pm_address=172.27.2.116 --pm_user=test --pm_password=password --prov_mac_address=98:4b:e1:67:9a:4c --terminal_port=8000

To verify the node registration, run 'nova-bm-manage node list'::

	$ nova-bm-manage node list
	ID        SERVICE_HOST  INSTANCE_ID   CPUS    Memory    Disk      PM_Address        PM_User           TERMINAL_PORT  PROV_MAC            PROV_VLAN
	1         bm1           None          4       6144      64        172.27.2.116      test              8000   98:4b:e1:67:9a:4c   None

To register a NIC, use 'nova-bm-manage interface create'.
It takes the parameters listed below.

* --node_id: ID of the baremetal node owns this NIC (the first column of 'nova-bm-manage node list')
* --mac_address: this NIC's MAC address in the form of xx:xx:xx:xx:xx:xx
* --datapath_id: datapath ID of OpenFlow switch this NIC is connected to
* --port_no: OpenFlow port number this NIC is connected to

(--datapath_id and --port_no are used for network isolation. It is OK to put 0, if you do not have OpenFlow switch.)

Example::

	$ nova-bm-manage interface create --node_id=1 --mac_address=98:4b:e1:67:9a:4e --datapath_id=0x123abc --port_no=24

To verify the NIC registration, run 'nova-bm-manage interface list'::

	$ nova-bm-manage interface list
	ID        BM_NODE_ID        MAC_ADDRESS         DATAPATH_ID       PORT_NO
	1         1                 98:4b:e1:67:9a:4e   0x123abc          24


Run Instance
=====

Run instance using the baremetal instance type.
Make sure to use kernel, ramdisk and image that support baremetal hardware (i.e contain drivers for baremetal hardware ).

Only partition images are currently supported. See 'How to create an image' section.

Example::

	euca-run-instances -t bm.small --kernel aki-AAA --ramdisk ari-BBB ami-CCC


How to create an image:
-----

Example: create a partition image from ubuntu cloud images' Precise tarball::

	$ wget http://cloud-images.ubuntu.com/precise/current/precise-server-cloudimg-amd64-root.tar.gz
	$ dd if=/dev/zero of=precise.img bs=1M count=0 seek=1024
	$ mkfs -F -t ext4 precise.img
	$ sudo mount -o loop precise.img /mnt/
	$ sudo tar -C /mnt -xzf ~/precise-server-cloudimg-amd64-root.tar.gz
	$ sudo mv /mnt/etc/resolv.conf /mnt/etc/resolv.conf_orig
	$ sudo cp /etc/resolv.conf /mnt/etc/resolv.conf
	$ sudo chroot /mnt apt-get install linux-image-3.2.0-26-generic vlan open-iscsi
	$ sudo mv /mnt/etc/resolv.conf_orig /mnt/etc/resolv.conf
	$ sudo umount /mnt
