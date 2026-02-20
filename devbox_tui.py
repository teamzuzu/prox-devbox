#!/usr/bin/env python3
"""
devbox TUI — interactive terminal interface for devbox.
Run from the project root:  python3 devbox_tui.py
"""

import os
import sys
import subprocess

# ── path setup ────────────────────────────────────────────────────────────────
_root = os.path.dirname(os.path.abspath(__file__))
sys.path[0:0] = [os.path.join(_root, 'lib')]
os.chdir(_root)  # devbox.ini and devbox.py live here

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label
from textual.widgets import ListItem, ListView, RichLog, Static
from textual import on, work
from rich.text import Text

# ── safe config import ────────────────────────────────────────────────────────
# Fake argv so devbox_config skips the "image must exist" check on import.
_saved_argv = sys.argv[:]
sys.argv = ['devbox.py', 'image', 'create']

_cfg = None
_cfg_error: str = ''

try:
    import devbox_config as _cfg
except SystemExit as _e:
    _cfg_error = f'Configuration failed (exit {_e.code}) — edit devbox.ini and restart'
except Exception as _e:
    _cfg_error = str(_e)
finally:
    sys.argv = _saved_argv


# ── data helpers ──────────────────────────────────────────────────────────────

def _has_cfg() -> bool:
    return _cfg is not None


def _node_rows() -> list[tuple[str, str, str, str]]:
    """Fresh (vmid, hostname, ip/mask, node) rows from the Proxmox API."""
    if not _has_cfg():
        return []
    try:
        rows = []
        for vm in _cfg.prox.cluster.resources.get(type='vm'):
            vid = int(vm.get('vmid'))
            if _cfg.dev_id <= vid < (_cfg.dev_id + 10) and vid != _cfg.dev_id:
                rows.append((
                    str(vid),
                    vm.get('name', ''),
                    f"{_cfg.vmip(vid)}/{_cfg.network_mask}",
                    vm.get('node', ''),
                ))
        return sorted(rows, key=lambda r: int(r[0]))
    except Exception:
        return []


def _node_list() -> list[tuple[int, str, str]]:
    """Fresh (vmid, hostname, ip/mask) list for the node picker modal."""
    if not _has_cfg():
        return []
    try:
        result = []
        for vm in _cfg.prox.cluster.resources.get(type='vm'):
            vid = int(vm.get('vmid'))
            if _cfg.dev_id <= vid < (_cfg.dev_id + 10) and vid != _cfg.dev_id:
                result.append((vid, vm.get('name', ''), f"{_cfg.vmip(vid)}/{_cfg.network_mask}"))
        return sorted(result)
    except Exception:
        return []


def _image_info() -> tuple[str, str]:
    """Return (description, storage_line) for the image panel."""
    if not _has_cfg():
        return ('', '')
    try:
        name = _cfg.devbox_img()
        if not name:
            return ('no image — run  Image › Create', '')
        tpl  = _cfg.prox.nodes(_cfg.node).qemu(_cfg.dev_id).config.get()
        desc = tpl.get('description', '')
        return (desc, f"{name}  ({_cfg.storage_type})")
    except Exception:
        return ('', '')


# ── modals ────────────────────────────────────────────────────────────────────

class NodePickerModal(ModalScreen):
    """Select an existing node by hostname."""

    DEFAULT_CSS = """
    NodePickerModal { align: center middle; }
    #picker-box {
        width: 54; max-height: 24;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #picker-title { text-style: bold; margin-bottom: 1; }
    ListView {
        height: auto; max-height: 14;
        border: solid $primary-darken-2;
    }
    #picker-cancel { margin-top: 1; width: 100%; }
    """

    def __init__(self, title: str, nodes: list[tuple[int, str, str]]) -> None:
        super().__init__()
        self._title = title
        self._nodes = nodes

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Label(self._title, id="picker-title")
            if self._nodes:
                yield ListView(
                    *[
                        ListItem(Label(f"  {name}   {ip}"), id=f"n-{vid}")
                        for vid, name, ip in self._nodes
                    ],
                    id="node-list",
                )
            else:
                yield Label("[dim]No nodes found[/dim]")
            yield Button("Cancel", id="picker-cancel", variant="default")

    @on(ListView.Selected)
    def selected(self, event: ListView.Selected) -> None:
        vid  = int(event.item.id.split("-", 1)[1])
        name = next(n for v, n, _ in self._nodes if v == vid)
        self.dismiss(name)

    @on(Button.Pressed, "#picker-cancel")
    def cancel(self) -> None:
        self.dismiss(None)


class CreateNodeModal(ModalScreen):
    """Enter a hostname for a new node."""

    DEFAULT_CSS = """
    CreateNodeModal { align: center middle; }
    #create-box {
        width: 54;
        border: thick $success;
        background: $surface;
        padding: 1 2;
    }
    #create-title  { text-style: bold; margin-bottom: 1; }
    #create-input  { margin-bottom: 1; }
    #create-row    { layout: horizontal; height: 3; }
    #create-ok     { width: 1fr; margin-right: 1; }
    #create-cancel { width: 1fr; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="create-box"):
            yield Label("Create node — enter hostname:", id="create-title")
            yield Input(placeholder="hostname", id="create-input")
            with Horizontal(id="create-row"):
                yield Button("Create", id="create-ok",     variant="success")
                yield Button("Cancel", id="create-cancel", variant="default")

    def _submit(self) -> None:
        val = self.query_one("#create-input", Input).value.strip()
        self.dismiss(val or None)

    @on(Button.Pressed,  "#create-ok")
    def ok(self)        -> None: self._submit()

    @on(Button.Pressed,  "#create-cancel")
    def cancel(self)    -> None: self.dismiss(None)

    @on(Input.Submitted)
    def submitted(self) -> None: self._submit()


# ── main application ──────────────────────────────────────────────────────────

class DevboxTUI(App):

    TITLE     = "devbox"
    SUB_TITLE = "Proxmox DevBox Manager"

    CSS = """
    /* ── global ── */
    Screen { layout: vertical; }

    /* ── main content row ── */
    #main { layout: horizontal; height: 1fr; }

    /* ── sidebar ── */
    #sidebar {
        width: 20;
        height: 100%;
        border-right: solid $primary-darken-2;
        background: $panel;
        padding: 0 1;
        overflow-y: auto;
    }
    .sec {
        text-style: bold;
        color: $primary;
        padding: 1 0 0 0;
        height: 2;
    }
    .sep { color: $primary-darken-2; height: 1; }
    Button { width: 100%; height: 3; margin: 0; }

    /* ── right pane ── */
    #right { width: 1fr; height: 100%; layout: vertical; }

    /* ── top split: node table + image info ── */
    #top-panels { layout: horizontal; height: 40%; }

    #nodes-panel {
        width: 2fr;
        border: solid $primary-darken-2;
    }
    #nodes-panel-title {
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
        height: 1;
        text-style: bold;
    }
    DataTable { height: 1fr; }

    #image-panel {
        width: 1fr;
        border: solid $accent-darken-2;
    }
    #image-panel-title {
        background: $accent-darken-2;
        color: $text;
        padding: 0 1;
        height: 1;
        text-style: bold;
    }
    #image-desc  { padding: 1 1 0 1; }
    #image-store { padding: 0 1;     color: $text-muted; }

    /* ── log panel ── */
    #log-panel { border: solid $surface-lighten-2; height: 1fr; }
    #log-panel-title {
        background: $surface-lighten-1;
        color: $text;
        padding: 0 1;
        height: 1;
        text-style: bold;
    }
    RichLog { height: 1fr; padding: 0 1; }

    /* ── status bar ── */
    #statusbar {
        height: 1;
        background: $primary-darken-3;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("r",      "refresh",   "Refresh"),
        Binding("ctrl+l", "clear_log", "Clear log"),
        Binding("q",      "quit",      "Quit"),
    ]

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main"):

            # sidebar
            with Vertical(id="sidebar"):
                yield Label("── Image ──", classes="sec")
                yield Button("Create",  id="img-create",  variant="success")
                yield Button("Info",    id="img-info")
                yield Button("Destroy", id="img-destroy", variant="error")

                yield Label("── Nodes ──", classes="sec")
                yield Button("Create",   id="nd-create",  variant="success")
                yield Button("Info",     id="nd-info")
                yield Button("SSH",      id="nd-ssh")
                yield Button("Terminal", id="nd-terminal")
                yield Button("Reboot",   id="nd-reboot")
                yield Button("Destroy",  id="nd-destroy", variant="error")

                yield Label("──────────", classes="sep")
                yield Button("⟳  Refresh", id="btn-refresh", variant="primary")

            # right pane
            with Vertical(id="right"):

                with Horizontal(id="top-panels"):

                    # node table
                    with Vertical(id="nodes-panel"):
                        yield Label(" Cluster Nodes", id="nodes-panel-title")
                        yield DataTable(id="nodes-table", cursor_type="row")

                    # image info
                    with Vertical(id="image-panel"):
                        yield Label(" Image", id="image-panel-title")
                        yield Label("", id="image-desc")
                        yield Label("", id="image-store")

                # log
                with Vertical(id="log-panel"):
                    yield Label(" Log", id="log-panel-title")
                    yield RichLog(id="log", highlight=True, markup=True, wrap=True)

        yield Static("", id="statusbar")
        yield Footer()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        t = self.query_one("#nodes-table", DataTable)
        t.add_columns("VMID", "Hostname", "IP / Mask", "Node")

        if not _has_cfg():
            self._log(f"[bold red]Config error:[/] {_cfg_error}")
            self._status("Config error — fix devbox.ini and restart", err=True)
        else:
            self._refresh_all()

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _log(self, msg) -> None:
        self.query_one("#log", RichLog).write(msg)

    def _status(self, msg: str, err: bool = False) -> None:
        colour = "red" if err else "green"
        self.query_one("#statusbar", Static).update(f"[{colour}]{msg}[/]")

    # ── actions ───────────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        if _has_cfg():
            self._refresh_all()

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    # ── background refresh ────────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        self._refresh_table()
        self._refresh_image()

    @work(thread=True)
    def _refresh_table(self) -> None:
        self.call_from_thread(self._status, "Refreshing…")
        rows = _node_rows()

        def _apply():
            t = self.query_one("#nodes-table", DataTable)
            t.clear()
            for row in rows:
                t.add_row(*row)
            n = len(rows)
            self._status(f"Ready — {n} node{'s' if n != 1 else ''}")

        self.call_from_thread(_apply)

    @work(thread=True)
    def _refresh_image(self) -> None:
        desc, store = _image_info()

        def _apply():
            self.query_one("#image-desc",  Label).update(desc  or "[dim]no image[/dim]")
            self.query_one("#image-store", Label).update(store or "")

        self.call_from_thread(_apply)

    # ── subprocess runner (non-interactive) ───────────────────────────────────

    @work(thread=True)
    def _run(self, args: list[str]) -> None:
        """Run devbox CLI as a subprocess and stream coloured output to the log."""
        label = "devbox " + " ".join(args)
        self.call_from_thread(self._log, f"\n[bold cyan]$ {label}[/]")
        self.call_from_thread(self._status, f"Running:  {label}")

        cmd = [sys.executable, os.path.join(_root, 'devbox.py')] + args
        env = {**os.environ, 'FORCE_COLOR': '1'}

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                cwd=_root,
            )
            log = self.query_one("#log", RichLog)
            for raw in proc.stdout:
                text = Text.from_ansi(raw.rstrip())
                self.call_from_thread(log.write, text)
            proc.wait()

            ok = proc.returncode == 0
            self.call_from_thread(
                self._status,
                f"Done:  {label}" if ok else f"Failed (rc={proc.returncode}):  {label}",
                not ok,
            )
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Error launching process: {e}[/]")
            self.call_from_thread(self._status, "Process error", True)

        # refresh status panels after any state-changing operation
        if len(args) > 1 and args[1] in ('create', 'destroy'):
            self.call_from_thread(self._refresh_all)

    # ── interactive runner (SSH / terminal — suspends TUI) ────────────────────

    def _run_interactive(self, args: list[str]) -> None:
        """Suspend the TUI, hand the terminal back, then resume."""
        cmd = [sys.executable, os.path.join(_root, 'devbox.py')] + args
        with self.suspend():
            subprocess.run(cmd, cwd=_root)

    # ── button handlers ───────────────────────────────────────────────────────

    @on(Button.Pressed, "#img-create")
    def h_img_create(self) -> None:
        self._run(['image', 'create'])

    @on(Button.Pressed, "#img-info")
    def h_img_info(self) -> None:
        self._run(['image', 'info'])

    @on(Button.Pressed, "#img-destroy")
    def h_img_destroy(self) -> None:
        self._run(['image', 'destroy'])

    @on(Button.Pressed, "#nd-info")
    def h_nd_info(self) -> None:
        self._run(['nodes', 'info'])

    @on(Button.Pressed, "#nd-create")
    async def h_nd_create(self) -> None:
        hostname = await self.push_screen_wait(CreateNodeModal())
        if hostname:
            self._run(['nodes', 'create', hostname])

    @on(Button.Pressed, "#nd-ssh")
    async def h_nd_ssh(self) -> None:
        nodes = _node_list()
        if not nodes:
            self._log("[yellow]No nodes available[/]")
            return
        hostname = await self.push_screen_wait(NodePickerModal("SSH to node", nodes))
        if hostname:
            self._run_interactive(['nodes', 'ssh', hostname])

    @on(Button.Pressed, "#nd-terminal")
    async def h_nd_terminal(self) -> None:
        nodes = _node_list()
        if not nodes:
            self._log("[yellow]No nodes available[/]")
            return
        hostname = await self.push_screen_wait(NodePickerModal("Open terminal on node", nodes))
        if hostname:
            self._run_interactive(['nodes', 'terminal', hostname])

    @on(Button.Pressed, "#nd-reboot")
    async def h_nd_reboot(self) -> None:
        nodes = _node_list()
        if not nodes:
            self._log("[yellow]No nodes available[/]")
            return
        hostname = await self.push_screen_wait(NodePickerModal("Reboot node", nodes))
        if hostname:
            self._run(['nodes', 'reboot', hostname])

    @on(Button.Pressed, "#nd-destroy")
    async def h_nd_destroy(self) -> None:
        nodes = _node_list()
        if not nodes:
            self._log("[yellow]No nodes available[/]")
            return
        hostname = await self.push_screen_wait(NodePickerModal("Destroy node", nodes))
        if hostname:
            self._run(['nodes', 'destroy', hostname])

    @on(Button.Pressed, "#btn-refresh")
    def h_refresh(self) -> None:
        self.action_refresh()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    DevboxTUI().run()
