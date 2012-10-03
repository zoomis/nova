Non-PXE (Tilera) Baremetal Instance Creation
============================================

1) A user requests a baremetal instance using tilera instance type.

::

  euca-run-instances -t tp64.8x8 -k my.key ami-CCC

2) nova-scheduler selects a baremetal nova-compute
   with the following configuration.

::

   Here we assume that
   $IP
      MySQL for baremetal DB runs at the machine whose IP address is $IP(127.0.0.1).
      It must be changed if a different IP address is used.
   $ID
     $ID should be replaced by MySQL user id
   $Password
     $Password should be replaced by MySQL password

::

  [nova.conf]
  baremetal_sql_connection=mysql://$ID:$Password@$IP/nova_bm
  compute_driver=nova.virt.baremetal.driver.BareMetalDriver
  baremetal_driver=tilera
  power_manager=tilera_pdu
  instance_type_extra_specs=cpu_arch:tilepro64
  baremetal_tftp_root = /tftpboot
  scheduler_host_manager=nova.scheduler.baremetal_host_manager.BaremetalHostManager

3) The bare-metal nova-compute selects a bare-metal node from its pool
   based on hardware resources and the instance type (# of cpus, memory, HDDs).

4) The key injected file system is prepared and then NFS directory is configured for the bare-metal nodes.
   The kernel is already put to CF(Compact Flash Memory) of each tilera board
   and the ramdisk is not used for the tilera bare-metal nodes.
   For NFS mounting, /tftpboot/fs_x (x=node_id) should be set before launching instances.

5) The baremetal nova-compute powers on the baremetal node thorough PDU(Power Distribution Unit).

6) The images are deployed to bare-metal nodes.
   nova-compute mounts AMI into NFS directory based on the id of the selected tilera bare-metal node.

7) The bare-metal node is configured for network, ssh, and iptables rule.

8) Done.
