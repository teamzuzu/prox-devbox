#!/usr/bin/env python3

# functions
from devbox_config import *
from devbox_proxmox import *

# passed command
cmd = sys.argv[2]

# map arg if passed
try:
  hostname = sys.argv[3]
except IndexError:
  pass

# define kname
kname = 'nodes_' + cmd

# all commands aside from create/info require a hostname - check them here
if cmd not in ['create', 'info']:

  # for each vmid in list of vms generated in devbox_config
  for vmid in vms:

    # if passed arg matches vmname
    if hostname == vmnames[vmid]:
      kmsg(kname, hostname)

      # terminal
      if cmd == 'terminal':
        kmsg('node_terminal', f'u/p: {cloudinituser} / {cloudinitpass}', 'sys')
        subprocess.run(['sudo', 'qm', 'terminal', str(vmid)])
        exit(0)

      # ssh command
      if cmd == 'ssh':
        subprocess.run([
          'ssh', '-l', cloudinituser, vmip(vmid),
          '-o', 'StrictHostKeyChecking=no',
        ])
        exit(0)

      # destroy vm
      if cmd == 'destroy':
        prox_destroy(vmid)
        exit(0)

      # reboot
      if cmd == 'reboot':
        subprocess.Popen(['sudo', 'qm', 'reboot', str(vmid)])
        exit(0)

  # vm not found
  kmsg(kname, f'{hostname} vm not found', 'err')

# create utility node
if cmd == 'create':

  # work out next highest available id
  node_id = int(max(vms) + 1)

  # check to see if already exists
  if hostname not in vmnames.values():
    node_id = int(max(vms) + 1)
    kmsg(kname, f'creating node {node_id}/{hostname}', 'sys')
    clone(node_id, hostname)
  else:
    kmsg(kname, f'node {hostname} already exists')
    devbox_info()

# info
if cmd == 'info':
  devbox_info()
