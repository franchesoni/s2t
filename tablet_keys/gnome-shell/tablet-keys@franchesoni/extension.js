import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

const BUTTONS = [
    ['F2', ['60:1', '60:0']],
    ['F3', ['61:1', '61:0']],
    ['F4', ['62:1', '62:0']],
    ['F9', ['67:1', '67:0']],
    ['Ctrl+C', ['29:1', '46:1', '46:0', '29:0']],
    ['Esc', ['1:1', '1:0']],
    ['Tab', ['15:1', '15:0']],
    ['/', ['53:1', '53:0']],
    ['Enter', ['28:1', '28:0']],
];

function shellQuote(value) {
    return `'${value.replace(/'/g, `'\\''`)}'`;
}

function sendYdotool(sequence) {
    const args = sequence.map(shellQuote).join(' ');
    const command = [
        'systemctl --user start ydotool.service >/dev/null 2>&1 || true',
        `ydotool key ${args} >/dev/null 2>&1 || ` +
            `YDOTOOL_SOCKET=/tmp/.ydotool_socket ydotool key ${args} >/dev/null 2>&1`,
    ].join('; ');

    GLib.spawn_command_line_async(`sh -c ${shellQuote(command)}`);
}

class TabletKeysPanel extends PanelMenu.Button {
    constructor() {
        super(0.0, 'Tablet Keys', false);

        this.add_style_class_name('tablet-keys-panel');

        const box = new St.BoxLayout({
            vertical: false,
            style_class: 'tablet-keys-box',
        });
        this.add_child(box);

        for (const [label, sequence] of BUTTONS) {
            const button = new St.Button({
                label,
                can_focus: false,
                reactive: true,
                track_hover: true,
                style_class: 'tablet-key-button',
                x_align: Clutter.ActorAlign.CENTER,
                y_align: Clutter.ActorAlign.CENTER,
            });

            button.connect('button-release-event', () => {
                sendYdotool(sequence);
                return Clutter.EVENT_STOP;
            });

            box.add_child(button);
        }
    }
}

export default class TabletKeysExtension extends Extension {
    enable() {
        this._indicator = new TabletKeysPanel();
        Main.panel.addToStatusArea('tablet-keys', this._indicator, 0, 'right');
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
