# Linux Speech-to-Text with Whisper

This project records microphone audio, transcribes it locally with OpenAI Whisper, and copies the result to the clipboard.

This checkout has been updated for GNOME on Wayland and uses `uv` to manage the Python/Whisper environment.

## Prerequisites

Install the system tools:

```bash
sudo apt update
sudo apt install ffmpeg wl-clipboard
```

Install `uv` if it is not already available:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

The scripts also work if `uv` is installed at `$HOME/.local/bin/uv`, even when that directory is not on `PATH`.

## Setup

From the repo directory:

```bash
$HOME/.local/bin/uv sync
chmod +x start_recording.sh stop_and_process_recording.sh toggle_recording.sh
```

`uv sync` installs Whisper into the repo-local `.venv`. The project is pinned to Python 3.12 and CPU-only PyTorch in `pyproject.toml`.

## Test

Run:

```bash
./start_recording.sh
```

Say something, then run:

```bash
./stop_and_process_recording.sh
```

The first transcription downloads the Whisper model. After transcription, the text is available on the clipboard.

## GNOME Shortcut

On GNOME Wayland, use a single toggle shortcut:

1. Open Settings.
2. Go to Keyboard > View and Customize Shortcuts > Custom Shortcuts.
3. Add a shortcut named `Speech to Text`.
4. Use this command:

```bash
/home/franchesoni/local/code/s2t/toggle_recording.sh
```

Press the shortcut once to start recording, then press it again to stop, transcribe, and copy to the clipboard.
Tap `F9`; do not hold it down. Wait about two seconds before tapping again to stop. The script debounces repeated shortcut events, but GNOME custom shortcuts are toggle-based rather than press/release-based.

Wayland does not allow the old `xdotool` automatic paste flow by default. Paste manually with `Ctrl+V` after the notification. On X11, set `S2T_AUTO_PASTE=1` if `xdotool` is installed and you want the old automatic paste behavior.

## Configuration

Environment variables:

- `S2T_ASR_BACKEND`: `whisper` or `azure`. If omitted, Azure is selected when `FOUNDRY_API_KEY` is present; otherwise Whisper is used.
- `FOUNDRY_API_KEY`: Azure Speech resource key. It can be stored in the ignored `.env` file.
- `S2T_AZURE_ENDPOINT`: Azure Speech endpoint. Defaults to `https://swedencentral.stt.speech.microsoft.com`; its regional hostname is mapped to Azure's fast-transcription REST hostname.
- `S2T_AZURE_LOCALES`: optional comma-separated locales such as `en-US,es-UY`; omitted means automatic detection.
- `S2T_WHISPER_MODEL`: Whisper model name. Defaults to `tiny`.
- `S2T_AUDIO_BACKEND`: ffmpeg input backend. Defaults to `pulse`.
- `S2T_AUDIO_INPUT`: ffmpeg input name. Defaults to `default`.
- `S2T_TMP_DIR`: temporary recording directory. Defaults to `./tmp`.
- `UV_BIN`: explicit `uv` path if needed.

To use cloud transcription with the Python toggle recorder, add this to `.env`:

```dotenv
S2T_ASR_BACKEND=azure
FOUNDRY_API_KEY=your-key
```

## Troubleshooting

If recording fails, check `tmp/ffmpeg.log`.

If transcription is slow, keep the default `tiny` model or try `S2T_WHISPER_MODEL=base` only if you want better accuracy and can wait longer.

If the shortcut works but nothing appears in the app, check the clipboard with:

```bash
wl-paste
```
