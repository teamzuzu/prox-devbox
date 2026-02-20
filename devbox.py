#!/usr/bin/env python3

import os, sys, importlib
sys.path[0:0] = ['lib/']
from devbox_ini import init_devbox_ini
from devbox_kmsg import kmsg

# check file exists
if not os.path.isfile('devbox.ini'):
  init_devbox_ini()
  exit(0)

# devbox verbs and commands
cmds = {
  "image": {
    "info" : '',
    "create" : '',
    "update": '',
    "destroy": '',
  },
  "nodes": {
    "info": '',
    "create" : 'hostname',
    "destroy" : 'hostname',
    "terminal" : 'hostname',
    "ssh" : 'hostname',
    "reboot" : 'hostname',
  }
}

# create list of verbs
verbs = list(cmds)

# print list of verbs
def verbs_help():
  kmsg('devbox_usage', '[verb] [command]')
  print('verbs:')
  for kverb in verbs:
    print(f'- {kverb}')

# print verbs cmds
def cmds_help(verb):
  kmsg(f'devbox_{verb}', '[command]')
  print('commands:')
  for verb_cmd in list(cmds[verb]):

    # if command with required arg
    if cmds[verb][verb_cmd]:
      print(f'- {verb_cmd} [{cmds[verb][verb_cmd]}]')
    else:
      print(f'- {verb_cmd}')

# handle verb parameter
try:

  # check for 1st argument
  if sys.argv[1]:

    # map 1st arg to verb
    verb = sys.argv[1]

    # if verb not found in cmds dict
    if verb not in verbs:
      kmsg('devbox_error', f'unknown verb: "{verb}"', 'err')
      verbs_help()
      exit(1)

# verb not found or passed
except IndexError:
  verbs_help()
  exit(0)

# handle command
try:

  # 2nd arg = cmd
  if sys.argv[2]:
    cmd = sys.argv[2]

    # if cmd not in list of commands
    if cmd not in list(cmds[verb]):
      kmsg('devbox_error', f'unknown command: "{cmd}"', 'err')
      cmds_help(verb)
      exit(1)

except IndexError:
  cmds_help(verb)
  exit(0)

# handle commands with required args eg 'node ssh hostname'
try:
  if cmds[verb][cmd] and sys.argv[3]:
    pass
except IndexError:
  kmsg(f'devbox_{verb}', f'{cmd} [{cmds[verb][cmd]}]')
  exit(0)

# run passed verb module (modules execute at import time)
importlib.import_module('verb_' + verb)
