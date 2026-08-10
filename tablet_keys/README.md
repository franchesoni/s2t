# Tablet Keys

Tablet-mode key buttons for `F2`, `F3`, `F4`, `F9`, `Ctrl+C`, `Esc`, `Tab`,
`/`, and `Enter`.

## GNOME Shell Extension

The focus-safe version is installed as a GNOME Shell extension:

```text
tablet-keys@franchesoni
```

It puts the buttons in the GNOME top panel. That keeps them visible above app
windows and avoids the focus-stealing behavior of a normal Wayland app window.

The extension is installed in:

```text
~/.local/share/gnome-shell/extensions/tablet-keys@franchesoni
```

Log out and back in after installing or changing it so GNOME Shell discovers
the extension.

## Fallback Window

The old GTK window is still available for quick testing:

```bash
/home/franchesoni/local/code/s2t/tablet_keys/tablet_keys.sh
```

It is not autostarted because normal app windows on GNOME Wayland can steal
focus or move behind other windows.

## ydotool

If button presses say `ydotoold not running`, start the daemon:

```bash
systemctl --user restart ydotool.service
```

For the current login session, the temporary root daemon can also be used:

```bash
sudo sh -c 'nohup ydotoold -P 0666 >/dev/null 2>&1 &'
```
