#!/usr/bin/env python3
"""Small touch-friendly function-key pad for tablet mode."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402


KEY_ROWS = [
    [
        ("F2", ["60:1", "60:0"]),
        ("F3", ["61:1", "61:0"]),
        ("F4", ["62:1", "62:0"]),
        ("F9", ["67:1", "67:0"]),
    ],
    [
        ("Ctrl+C", ["29:1", "46:1", "46:0", "29:0"]),
        ("Esc", ["1:1", "1:0"]),
        ("Tab", ["15:1", "15:0"]),
        ("/", ["53:1", "53:0"]),
        ("Enter", ["28:1", "28:0"]),
    ],
]


@dataclass
class CommandResult:
    ok: bool
    message: str


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_quiet(cmd: list[str], env: dict[str, str] | None = None) -> bool:
    command_env = os.environ.copy()
    if env:
        command_env.update(env)
    try:
        subprocess.run(
            cmd,
            env=command_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.5,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def send_key_sequence(sequence: list[str]) -> CommandResult:
    if not command_exists("ydotool"):
        return CommandResult(False, "Install ydotool")

    run_quiet(["systemctl", "--user", "start", "ydotool.service"])
    cmd = ["ydotool", "key", *sequence]
    if run_quiet(cmd):
        return CommandResult(True, "Sent")
    if run_quiet(cmd, {"YDOTOOL_SOCKET": "/tmp/.ydotool_socket"}):
        return CommandResult(True, "Sent")
    return CommandResult(False, "ydotoold not running")


class TabletKeys(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="Keys")
        self.set_keep_above(True)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_skip_taskbar_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_resizable(False)
        self.set_border_width(8)
        self.connect("destroy", Gtk.main_quit)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(box)

        for key_row in KEY_ROWS:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.pack_start(row, True, True, 0)

            for label, sequence in key_row:
                button = Gtk.Button(label=label)
                button.set_size_request(78, 54)
                button.get_style_context().add_class("tablet-key")
                button.connect("clicked", self.on_key_clicked, label, sequence)
                row.pack_start(button, True, True, 0)

        self.status = Gtk.Label(label="")
        self.status.set_xalign(0.5)
        box.pack_start(self.status, False, False, 0)

        css = b"""
        window {
          background: #f1f3f4;
        }
        button.tablet-key {
          background: #ffffff;
          color: #000000;
          font-size: 20px;
          font-weight: 700;
          padding: 8px 12px;
        }
        label {
          color: #000000;
          font-size: 11px;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def on_key_clicked(self, _button: Gtk.Button, label: str, sequence: list[str]) -> None:
        self.status.set_text(f"{label}...")
        # Let the button release finish before injecting the synthetic key.
        GLib.timeout_add(80, self.send_key, label, sequence)

    def send_key(self, label: str, sequence: list[str]) -> bool:
        result = send_key_sequence(sequence)
        self.status.set_text(f"{label}: {result.message}")
        GLib.timeout_add(1200, self.clear_status)
        return False

    def clear_status(self) -> bool:
        self.status.set_text("")
        return False


def main() -> int:
    window = TabletKeys()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
