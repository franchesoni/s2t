# ASR Recorder

Keyboard-shortcut-friendly recording with local Whisper or Azure Speech transcription.

Use one shortcut command to start when idle and stop when recording:

```bash
/home/franchesoni/local/code/s2t/src/toggle_recorder.sh
```

Or call the Python CLI directly:

```bash
python3 /home/franchesoni/local/code/s2t/src/asr_recorder.py toggle
```

Press the shortcut once to start recording. Press it again to stop recording,
run Whisper, copy the transcript to the clipboard, paste it with `Ctrl+V`, wait
one second, and press `Enter`.

Recordings and transcripts are saved under `tmp/` by default, using names like:

```text
recording_20260528_134501.wav
recording_20260528_134501.txt
```

On Ubuntu GNOME, bind the toggle command above in:

```text
Settings > Keyboard > View and Customize Shortcuts > Custom Shortcuts
```

For example:

- `Ctrl+Alt+R` -> `/home/franchesoni/local/code/s2t/src/toggle_recorder.sh`

On GNOME Wayland, install `ydotool` for automatic paste:

```bash
sudo apt install ydotool
sudo usermod -aG input "$USER"
```

Log out and back in after adding the group. If paste still does not fire, run:

```bash
systemctl --user restart ydotool.service
```

The visible recorder and transcription progress windows use `zenity` when
available. If `zenity` is not installed, the recorder still runs and uses
desktop notifications only.

Configuration:

- `S2T_ASR_BACKEND=whisper` selects local Whisper. It is the default when no Azure key is configured.
- `S2T_ASR_BACKEND=azure` selects Azure Speech fast transcription and loads `FOUNDRY_API_KEY` from `.env`. Azure is selected automatically when that key is present.
- `S2T_AZURE_ENDPOINT` defaults to `https://swedencentral.stt.speech.microsoft.com`; its regional hostname is mapped to Azure's fast-transcription REST hostname.
- `S2T_AZURE_LOCALES=en-US` optionally specifies one or more comma-separated locales. If omitted, Azure detects the language.
- `S2T_AUTO_PASTE=0` disables automatic paste.
- `S2T_SHOW_TRANSCRIPT=1` also opens the final transcript window.
- `S2T_PASTE_DELAY_SECONDS=0.15` controls the delay before sending `Ctrl+V`.
- `S2T_SUBMIT_DELAY_SECONDS=1` controls the delay between pasting and pressing `Enter`.
