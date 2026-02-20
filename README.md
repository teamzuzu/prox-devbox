# prox-devbox

A lightweight CLI (and TUI) for spinning up ephemeral Ubuntu development VMs on a Proxmox VE node. Each devbox is a thin clone of a shared cloud-image template, pre-configured with cloud-init, a static IP, and a QEMU guest agent.

---

## How it works

1. A single Ubuntu cloud image is downloaded, customised, and registered as a Proxmox template (`image create`).
2. Every devbox is a linked clone of that template, assigned the next free IP in a configured range (`nodes create`).
3. All VMs share the same cloud-init user, password, and SSH key defined in `devbox.ini`.

---

## Requirements

| Requirement | Notes |
|---|---|
| Python 3.9+ | Runs on the machine that issues commands |
| Proxmox VE 7+ | API access required |
| Proxmox API token | `root@pam` or a dedicated user with VM.* privileges |
| `virt-customize` | `apt install libguestfs-tools` on the Proxmox node |
| `sudo` / `qm` access | For disk import and template conversion |

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Quick start

### 1. Clone and configure

```bash
git clone https://github.com/teamzuzu/prox-devbox
cd prox-devbox
```

Run the CLI once to generate a blank `devbox.ini`:

```bash
python3 devbox.py
```

Edit `devbox.ini` — the key fields are described below.

### 2. Create the base image

Downloads the Ubuntu cloud image, installs `qemu-guest-agent`, and registers a Proxmox template:

```bash
python3 devbox.py image create
```

This only needs to be run once (or when you want to refresh the base image).

### 3. Create a devbox

```bash
python3 devbox.py nodes create mydev
```

The VM is cloned, configured, started, and verified to have internet access before the command returns.

---

## Configuration (`devbox.ini`)

Generated automatically on first run. Edit before calling `image create`.

### `[proxmox]`

| Key | Description | Example |
|---|---|---|
| `prox_endpoint` | Proxmox host (IP or hostname) | `192.168.0.10` |
| `port` | API port | `8006` |
| `user` | Proxmox user with API token | `root@pam` |
| `token_name` | API token name | `devbox` |
| `api_key` | API token value | `xxxxxxxx-xxxx-...` |
| `node` | Proxmox node to create VMs on | `pve` |
| `storage` | Storage pool for VM disks | `local-lvm` |

### `[devbox]`

| Key | Description | Example |
|---|---|---|
| `dev_id` | Base Proxmox VM ID (must be > 100). The template gets this ID; nodes get `dev_id+1`, `dev_id+2`, … | `600` |
| `cloud_image_url` | URL of the upstream Ubuntu cloud image | *(default: Ubuntu Oracular minimal)* |
| `vm_cpu` | CPU cores per VM | `1` |
| `vm_ram` | RAM in GB per VM | `2` |
| `vm_disk` | Disk size in GB per VM | `20` |
| `cloudinituser` | Username created by cloud-init | `dev` |
| `cloudinitpass` | Password for the cloud-init user | `changeme` |
| `cloudinitsshkey` | SSH public key for the cloud-init user | `ssh-ed25519 AAAA…` |
| `network_bridge` | Proxmox bridge (or `sdn/zone/vnet` for SDN) | `vmbr0` |
| `network_ip` | First IP in the devbox range (assigned to the template) | `192.168.0.160` |
| `network_mask` | CIDR prefix length | `24` |
| `network_gw` | Default gateway | `192.168.0.1` |
| `network_dns` | DNS server | `192.168.0.1` |
| `network_mtu` | Interface MTU (use `1450` for SDN/VXLAN) | `1500` |

#### IP assignment

IPs are assigned sequentially starting from `network_ip`:

```
dev_id+0  →  network_ip+0  (template — not a usable devbox)
dev_id+1  →  network_ip+1  (first devbox)
dev_id+2  →  network_ip+2
…
dev_id+9  →  network_ip+9  (max 9 devboxes per cluster)
```

#### SDN / VXLAN networks

Set `network_bridge = sdn/zone/vnet` and `network_mtu = 1450`.

---

## CLI reference

```
python3 devbox.py <verb> <command> [hostname]
```

### Image commands

| Command | Description |
|---|---|
| `image create` | Download cloud image, customise it, register as Proxmox template |
| `image info` | Show template description and storage details |
| `image destroy` | Delete the template VM |

### Node commands

| Command | Description |
|---|---|
| `nodes create <hostname>` | Clone template → new VM with next available IP |
| `nodes info` | List all devbox VMs with their IPs and Proxmox node |
| `nodes ssh <hostname>` | Open an SSH session to the VM |
| `nodes terminal <hostname>` | Open a serial console via `qm terminal` |
| `nodes reboot <hostname>` | Reboot the VM |
| `nodes destroy <hostname>` | Power off and delete the VM |

---

## TUI

An interactive terminal UI is available as an alternative to the CLI:

```bash
python3 devbox_tui.py
```

Requires `textual>=0.50.0` (included in `requirements.txt`).

```
┌─ devbox ─ Proxmox DevBox Manager ─────────────────────────────────────────┐
│ ┌── Image ───┐  ┌── Cluster Nodes ──────────────────┐ ┌── Image ─────────┐│
│ │ Create     │  │ VMID  Hostname  IP / Mask   Node  │ │ devbox 2024-...  ││
│ │ Info       │  │ 601   dev1      .161/24     pve   │ │ local-lvm/vm-600 ││
│ │ Destroy    │  │ 602   dev2      .162/24     pve   │ └──────────────────┘│
│ ├── Nodes ───┤  └──────────────────────────────────-┘                     │
│ │ Create     │  ┌── Log ───────────────────────────────────────────────── ┐│
│ │ Info       │  │ $ devbox nodes create dev3                              ││
│ │ SSH        │  │ proxmox:clone: dev3 192.168.0.163/24 1c/2G ram 20G disk ││
│ │ Terminal   │  │ ...                                                     ││
│ │ Reboot     │  └─────────────────────────────────────────────────────────┘│
│ │ Destroy    │                                                              │
│ ├────────────┤                                                              │
│ │ ⟳ Refresh  │                                                              │
└─┴────────────┴──────────────────────────────────────────────────────────── ┘
  r Refresh    ctrl+l Clear log    q Quit
```

**Features:**
- Live VM table refreshed automatically after every create/destroy
- Node picker modal for operations that require a hostname (SSH, terminal, reboot, destroy)
- Hostname input modal for creating new nodes
- Command output streamed in real time with colours preserved
- SSH and terminal sessions suspend the TUI and restore it cleanly on exit

---

## Project structure

```
prox-devbox/
├── devbox.py          # CLI entry point
├── devbox_tui.py      # TUI entry point
├── devbox.ini         # Your config (git-ignored, auto-generated on first run)
├── devbox.ini.default # Config template for reference
├── requirements.txt
└── lib/
    ├── devbox_config.py   # Config loading, Proxmox connection, shared state
    ├── devbox_proxmox.py  # Proxmox API wrappers (clone, destroy, exec, tasks)
    ├── devbox_ini.py      # Generates the default devbox.ini
    ├── devbox_kmsg.py     # Coloured log output helper
    ├── verb_image.py      # Implements `image` commands
    └── verb_nodes.py      # Implements `nodes` commands
```
