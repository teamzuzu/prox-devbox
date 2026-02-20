#!/usr/bin/env python3

import shlex

# devbox
from devbox_config import *

# run a exec via qemu-agent
def qaexec(vmid: int, cmd='uptime', node: str = node):

  # define kname
  kname = 'qaexec'

  # get node from vm map
  try:
    node = vms[vmid]
  except KeyError:
    pass

  # qagent not yet running check
  qagent_running = False

  # max wait time
  qagent_count = 1

  # wait until qemu-agent responds
  while not qagent_running:
    try:
      prox.nodes(node).qemu(vmid).agent.ping.post()
      qagent_running = True

    except Exception:
      qagent_count += 1

      # exit if longer than 30 seconds
      if qagent_count >= 30:
        vmname = vmnames.get(vmid, str(vmid))
        kmsg(kname, f'agent not responding on {vmname} [{node}] cmd: {cmd}', 'err')
        exit(1)

      # sleep 1 second then try again
      time.sleep(1)

  # send command via qemu-agent exec (use sh -c for shell features)
  try:
    qa_exec = prox.nodes(node).qemu(vmid).agent.exec.post(
      command=f'sh -c {shlex.quote(cmd)}',
    )
  except Exception as e:
    kmsg(kname, f'{vmid}: problem running cmd: {cmd} - {e}', 'err')
    exit(1)

  # get pid
  pid = qa_exec['pid']
  pid_status = 0

  # loop until command has finished
  while pid_status != 1:
    try:
      pid_check = prox.nodes(node).qemu(vmid).agent('exec-status').get(pid=pid)
    except Exception as e:
      kmsg(kname, f'{vmid}: problem checking pid {pid}: {e}', 'err')
      exit(1)

    # will equal 1 when process is done
    pid_status = pid_check['exited']
    if not pid_status:
      time.sleep(0.5)

  # check for exitcode 127 (command not found)
  if int(pid_check['exitcode']) == 127:
    kmsg(kname, f'{vmid}: exit code 127 (command not found): {cmd}', 'err')
    exit(1)

  # check for stderr output
  if pid_check.get('err-data'):
    kmsg('qaexec_stderr', f'CMD: {cmd}\n{pid_check["err-data"].strip()}', 'err')

    # if there is stdout alongside stderr, return it
    if pid_check.get('out-data'):
      return pid_check['out-data'].strip()
    else:
      exit(1)

  # return stdout if present
  if pid_check.get('out-data'):
    return pid_check['out-data'].strip()

  return f'no output - {cmd}'

# stop and destroy vm
def prox_destroy(vmid: int):

  kname = 'destroy_devbox'

  # if destroying image
  if vmid == dev_id:
    prox_task(prox.nodes(node).qemu(dev_id).delete())
    return

  # power off and delete
  try:
    prox_task(prox.nodes(node).qemu(vmid).status.stop.post(), node)
    prox_task(prox.nodes(node).qemu(vmid).delete(), node)
    kmsg(kname, vmnames[vmid])
  except Exception as e:
    kmsg(kname, f'unable to destroy {node}/{vmid}: {e}', 'err')
    exit(1)

# clone
def clone(vmid: int, hostname: str):

  # map network info
  ip = vmip(vmid) + '/' + network_mask

  # vm ram convert from G to MB
  memory = vm_ram * 1024

  # hostname
  kmsg('proxmox_clone', f'{hostname} {ip} {vm_cpu}c/{vm_ram}G ram {vm_disk}G disk')

  # clone
  prox_task(prox.nodes(node).qemu(dev_id).clone.post(newid=vmid))

  # configure
  prox_task(prox.nodes(node).qemu(vmid).config.post(
    name=hostname,
    onboot=1,
    cores=vm_cpu,
    memory=memory,
    balloon='0',
    boot='order=scsi0',
    net0=f'model=virtio,bridge={network_bridge},mtu={network_mtu}',
    ipconfig0=f'gw={network_gw},ip={ip}',
    nameserver=network_dns,
    description=f'{vmid}:{hostname}:{ip}',
  ))

  # resize disk
  prox_task(prox.nodes(node).qemu(vmid).resize.put(
    disk='scsi0',
    size=f'{vm_disk}G',
  ))

  # power on
  prox_task(prox.nodes(node).qemu(vmid).status.start.post())

  # wait for qemu-agent and verify network access
  internet_check(vmid)

# proxmox task blocker - waits for an async task to complete
def prox_task(task_id, node=node):

  # poll until task is stopped
  try:
    status = {"status": ""}
    while status["status"] != "stopped":
      status = prox.nodes(node).tasks(task_id).status.get()
      if status["status"] != "stopped":
        time.sleep(1)
  except Exception as e:
    kmsg('proxmox_task-status', f'unable to get task status for {task_id} on node {node}: {e}', 'err')
    exit(1)

  # if task not completed ok
  if status["exitstatus"] != "OK":
    log = task_log(task_id)
    kmsg('proxmox_task-status', f'task exited with non-OK status ({status["exitstatus"]})\n{log}', 'err')
    exit(1)

# returns the task log as a string
def task_log(task_id, node=node):

  try:
    lines = [log['t'] for log in prox.nodes(node).tasks(task_id).log.get()]
    return '\n'.join(lines)
  except Exception as e:
    kmsg('proxmox_task-log', f'failed to get log for task {task_id}: {e}', 'err')
    exit(1)

# internet checker - verifies vm has outbound network access
def internet_check(vmid):
  internet_cmd = 'curl -s --retry 2 --retry-all-errors --connect-timeout 1 --max-time 2 www.google.com > /dev/null && echo ok || echo error'
  result = qaexec(vmid, internet_cmd)

  # if curl command fails
  if result == 'error':
    vmname = vmnames.get(vmid, str(vmid))
    kmsg('prox_netcheck', f'{vmname} internet access check failed', 'err')
    exit(1)
