#!/usr/bin/env python3

# functions
from devbox_config import *

# proxmox functions
from devbox_proxmox import prox_task, prox_destroy

# define command
cmd = sys.argv[2]
kname = 'image_'

# create image
if cmd == 'create':

  # get image name from url
  cloud_image = cloud_image_url.split('/')[-1]
  kmsg(f'{kname}create', f'{cloud_image} {storage}/{dev_id}', 'sys')

  # check if image already exists and remove it
  if os.path.isfile(cloud_image):
    kmsg('image_check', f'{cloud_image} already exists - removing', 'sys')
    try:
      os.remove(cloud_image)
      if os.path.isfile(cloud_image):
        kmsg(f'{kname}check', f'{cloud_image} still exists after removal', 'err')
        exit(1)
    except OSError as e:
      kmsg(f'{kname}check', f'{cloud_image} cannot delete: {e}', 'err')
      exit(1)

  # download cloud image
  try:
    kmsg(f'{kname}wget', f'{cloud_image_url}')
    wget.download(cloud_image_url)
    print()
  except Exception as e:
    kmsg(f'{kname}check', f'unable to download {cloud_image_url}: {e}', 'err')
    exit(1)

  # install qemu-guest-agent into the image
  kmsg(f'{kname}virt-customize', 'configuring image')
  virtc_cmd = f'sudo virt-customize -a {cloud_image} --install qemu-guest-agent'
  local_os_process(virtc_cmd)

  # define image desc
  img_ts = str(datetime.now())
  image_desc = f'devbox {img_ts}'

  # destroy existing template if it exists
  try:
    prox_destroy(dev_id)
  except Exception:
    pass

  # create new template vm
  prox_task(prox.nodes(node).qemu.post(
    vmid=dev_id,
    cores=1,
    memory=1024,
    bios='ovmf',
    efidisk0=f'{storage}:0',
    machine='q35',
    cpu='cputype=x86-64-v3',
    scsihw='virtio-scsi-single',
    name='devboximg',
    ostype='l26',
    scsi2=f'{storage}:cloudinit',
    serial0='socket',
    agent='enabled=true',
    hotplug=0,
    ciupgrade=0,
    description=image_desc,
    ciuser=cloudinituser,
    cipassword=cloudinitpass,
    sshkeys=cloudinitsshkey,
  ))

  # import disk - requires full path for import-from
  import_cmd = f'sudo qm set {dev_id} --scsi0 {storage}:0,import-from={os.getcwd()}/{cloud_image},iothread=true,aio=io_uring && mv {cloud_image} {cloud_image}.patched'
  local_os_process(import_cmd)

  # convert to template
  prox_task(prox.nodes(node).qemu(dev_id).template.post())
  prox_task(prox.nodes(node).qemu(dev_id).config.post(template=1))
  kmsg(f'{kname}qm-import', 'done')

# image info
if cmd == 'info':
  image_info()

# destroy image
if cmd == 'destroy':
  kmsg(f'{kname}destroy', f'{devbox_img()}/{cloud_image_desc}', 'sys')
  prox_destroy(dev_id)
