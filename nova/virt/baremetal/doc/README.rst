General Bare-metal Provisioning README
=====

:Authors: mkkang@isi.edu, dkang@isi.edu, openstack-contributor-ml@nttdocomo.com
:Date:   2012-08-01
:Version: 2012.8
:Wiki: http://wiki.openstack.org/GeneralBareMetalProvisioningFramework

Code changes
-----

::
 
  nova/nova/virt/baremetal/*
  nova/nova/tests/baremetal/*
  nova/nova/scheduler/baremetal_host_manager.py
  nova/nova/tests/scheduler/test_baremetal_host_manager.py
  nova/bin/bm*

Additional setting for bare-metal provisioning [nova.conf]
-----

::

  # baremetal database connection
  baremetal_sql_connection = mysql://$ID:$Password@$IP/nova_bm
  
  # baremetal compute driver
  compute_driver = nova.virt.baremetal.driver.BareMetalDriver
  baremetal_driver = {tilera | pxe}
  power_manager = {tilera_pdu | ipmi}
  
  # instance_type_extra_specs this baremetal compute
  instanse_type_extra_specs = cpu_arch:{tilepro64 | x86_64 | arm}
  
  # TFTP root
  baremetal_tftp_root = /tftpboot
  
  # baremetal scheduler host manager
  scheduler_host_manager = nova.scheduler.baremetal_host_manager.BaremetalHostManager


Non-PXE (Tilera) Bare-metal Provisioning
-----

1. tilera-bm-instance-creation.rst

2. tilera-bm-installation.rst 

PXE Bare-metal Provisioning
-----

1. pxe-bm-instance-creation.rst

2. pxe-bm-installation.rst

