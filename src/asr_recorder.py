#!/usr/bin/env python3
"""Small start/stop recorder for Ubuntu custom keyboard shortcuts."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TMP_DIR = PROJECT_ROOT / "tmp"
STATE_FILE_NAME = "asr_recorder_state.json"
LOCK_FILE_NAME = "asr_recorder.lock"
DEFAULT_AZURE_SPEECH_ENDPOINT = "https://swedencentral.stt.speech.microsoft.com"
AZURE_SPEECH_API_VERSION = "2025-10-15"


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding the process environment."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[:1] == value[-1:] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def tmp_dir() -> Path:
    return Path(os.environ.get("S2T_TMP_DIR", DEFAULT_TMP_DIR)).expanduser().resolve()


def state_file(directory: Path) -> Path:
    return directory / STATE_FILE_NAME


def lock_file(directory: Path) -> Path:
    return directory / LOCK_FILE_NAME


@contextlib.contextmanager
def state_lock(directory: Path) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    with lock_file(directory).open("w") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("asr-recorder: another recorder command is already running.", file=sys.stderr)
            raise SystemExit(1)
        yield


def load_state(directory: Path) -> dict[str, Any] | None:
    path = state_file(directory)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_state(directory: Path, state: dict[str, Any]) -> None:
    state_file(directory).write_text(json.dumps(state, indent=2), encoding="utf-8")


def clear_state(directory: Path) -> None:
    state_file(directory).unlink(missing_ok=True)


def active_state(current: dict[str, Any] | None) -> dict[str, Any] | None:
    if not current:
        return None
    if pid_is_running(current.get("ffmpeg_pid")):
        return current | {"phase": "recording"}
    if pid_is_running(current.get("transcriber_pid")):
        return current | {"phase": "transcribing"}
    return None


def load_active_state(directory: Path) -> dict[str, Any] | None:
    current = active_state(load_state(directory))
    if not current:
        clear_state(directory)
    return current


def pid_is_running(pid: Any) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def notify(title: str, body: str) -> None:
    if command_exists("notify-send"):
        subprocess.Popen(
            ["notify-send", title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def print_log_excerpt(log_file: Path) -> None:
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    for line in lines[:20]:
        print(f"  {line}", file=sys.stderr)


def timestamped_audio_path(directory: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return directory / f"recording_{timestamp}.wav"


def start_visible_indicator(audio_file: Path) -> int | None:
    if not command_exists("zenity"):
        notify("ASR Recorder", f"Recording started: {audio_file.name}")
        return None

    script = f"""
while true; do
  printf '# Recording audio...\\n'
  sleep 1
done | zenity --progress --pulsate --no-cancel --width=360 \\
  --title='ASR Recorder' \\
  --text='Recording...
Press your stop shortcut to finish.
{audio_file.name}'
"""
    proc = subprocess.Popen(
        ["bash", "-lc", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc.pid


def start_transcription_indicator(audio_file: Path, backend: str) -> int | None:
    if not command_exists("zenity"):
        notify("ASR Recorder", f"Transcribing {audio_file.name}")
        return None

    script = f"""
while true; do
  printf '# Running {backend} transcription...\\n'
  sleep 1
done | zenity --progress --pulsate --no-cancel --width=380 \\
  --title='ASR Recorder' \\
  --text='Transcribing...
{audio_file.name}'
"""
    proc = subprocess.Popen(
        ["bash", "-lc", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc.pid


def signal_process(pid: int | None, sig: signal.Signals) -> None:
    if not pid:
        return
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return
    except OSError:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return


def wait_for_exit(pid: int | None, timeout_seconds: float) -> bool:
    if not pid:
        return True
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not pid_is_running(pid):
            return True
        time.sleep(0.1)
    return not pid_is_running(pid)


def uv_bin() -> str | None:
    explicit = os.environ.get("UV_BIN")
    if explicit:
        return explicit
    discovered = shutil.which("uv")
    if discovered:
        return discovered
    fallback = Path.home() / ".local" / "bin" / "uv"
    if fallback.exists():
        return str(fallback)
    return None


def copy_to_clipboard(text_file: Path) -> bool:
    if command_exists("wl-copy") and os.environ.get("XDG_SESSION_TYPE") == "wayland":
        cmd = ["wl-copy"]
    elif command_exists("xclip"):
        cmd = ["xclip", "-selection", "clipboard"]
    else:
        print("asr-recorder: install wl-clipboard or xclip to copy text.", file=sys.stderr)
        return False

    try:
        with text_file.open("rb") as text:
            subprocess.run(cmd, stdin=text, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"asr-recorder: clipboard copy failed: {exc}", file=sys.stderr)
        return False
    return True


def show_transcription(text_file: Path) -> None:
    if not command_exists("zenity"):
        return

    try:
        subprocess.Popen(
            [
                "zenity",
                "--text-info",
                "--width=700",
                "--height=420",
                "--title=Whisper transcription",
                f"--filename={text_file}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        print(f"asr-recorder: could not show transcription window: {exc}", file=sys.stderr)


def auto_paste_enabled() -> bool:
    return os.environ.get("S2T_AUTO_PASTE", "1") != "0"


def show_transcript_enabled() -> bool:
    return os.environ.get("S2T_SHOW_TRANSCRIPT", "0") == "1"


def paste_delay_seconds() -> float:
    try:
        return float(os.environ.get("S2T_PASTE_DELAY_SECONDS", "0.15"))
    except ValueError:
        return 0.15


def run_paste_command(cmd: list[str], env: dict[str, str] | None = None) -> bool:
    command_env = os.environ.copy()
    if env:
        command_env.update(env)
    try:
        subprocess.run(
            cmd,
            env=command_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"asr-recorder: paste command failed: {' '.join(cmd)}: {exc}", file=sys.stderr)
        return False
    return True


def paste_from_clipboard() -> bool:
    if not auto_paste_enabled():
        return False

    time.sleep(paste_delay_seconds())
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    if session_type == "x11" and command_exists("xdotool"):
        return run_paste_command(["xdotool", "key", "--clearmodifiers", "ctrl+v"])

    if command_exists("wtype"):
        if run_paste_command(["wtype", "-M", "ctrl", "v", "-m", "ctrl"]):
            return True

    if command_exists("ydotool"):
        run_paste_command(["systemctl", "--user", "start", "ydotool.service"])
        ydotool_cmd = ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]
        if run_paste_command(ydotool_cmd):
            return True
        return run_paste_command(ydotool_cmd, {"YDOTOOL_SOCKET": "/tmp/.ydotool_socket"})

    print("asr-recorder: no paste tool found. Install ydotool for GNOME Wayland.", file=sys.stderr)
    return False


def clear_transcription_state(directory: Path) -> None:
    try:
        with state_lock(directory):
            current = load_state(directory)
            if current and current.get("transcriber_pid") == os.getpid():
                clear_state(directory)
    except SystemExit:
        pass


def azure_multipart_body(audio_file: Path, definition: dict[str, Any]) -> tuple[bytes, str]:
    boundary = f"----s2t-{uuid.uuid4().hex}"
    crlf = b"\r\n"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="definition"\r\n')
    body.extend(b"Content-Type: application/json\r\n\r\n")
    body.extend(json.dumps(definition).encode("utf-8"))
    body.extend(crlf)
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="audio"; filename="{audio_file.name}"\r\n'.encode()
    )
    body.extend(b"Content-Type: audio/wav\r\n\r\n")
    body.extend(audio_file.read_bytes())
    body.extend(crlf)
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), boundary


def azure_fast_endpoint(endpoint: str) -> str:
    """Convert a regional real-time Speech hostname to its fast REST hostname."""
    endpoint = endpoint.rstrip("/")
    suffix = ".stt.speech.microsoft.com"
    if endpoint.endswith(suffix):
        endpoint = endpoint[: -len(suffix)] + ".api.cognitive.microsoft.com"
    return endpoint


def transcribe_with_azure(audio_file: Path, text_file: Path, log_file: Path) -> int:
    api_key = os.environ.get("FOUNDRY_API_KEY")
    if not api_key:
        print("asr-recorder: FOUNDRY_API_KEY is not set.", file=sys.stderr)
        return 1

    endpoint = azure_fast_endpoint(os.environ.get("S2T_AZURE_ENDPOINT", DEFAULT_AZURE_SPEECH_ENDPOINT))
    url = f"{endpoint}/speechtotext/transcriptions:transcribe?api-version={AZURE_SPEECH_API_VERSION}"
    locales = [item.strip() for item in os.environ.get("S2T_AZURE_LOCALES", "").split(",") if item.strip()]
    definition: dict[str, Any] = {}
    if locales:
        definition["locales"] = locales
    body, boundary = azure_multipart_body(audio_file, definition)
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        log_file.write_text(f"HTTP {exc.code}\n{details}\n", encoding="utf-8")
        print(f"asr-recorder: Azure transcription failed (HTTP {exc.code}). See {log_file}", file=sys.stderr)
        return 1
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        log_file.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        print(f"asr-recorder: Azure transcription failed. See {log_file}", file=sys.stderr)
        return 1

    phrases = payload.get("combinedPhrases", [])
    transcript = "\n".join(
        phrase.get("text", "").strip()
        for phrase in phrases
        if isinstance(phrase, dict) and phrase.get("text", "").strip()
    )
    if not transcript:
        log_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"asr-recorder: Azure returned no transcript. See {log_file}", file=sys.stderr)
        return 1
    text_file.write_text(transcript + "\n", encoding="utf-8")
    return 0


def transcribe_audio(audio_file: Path, directory: Path) -> int:
    default_backend = "azure" if os.environ.get("FOUNDRY_API_KEY") else "whisper"
    backend = os.environ.get("S2T_ASR_BACKEND", default_backend).lower()
    text_file = audio_file.with_suffix(".txt")
    log_file = audio_file.with_suffix(f".{backend}.log")
    text_file.unlink(missing_ok=True)

    indicator_pid = start_transcription_indicator(audio_file, backend)
    try:
        if backend == "azure":
            returncode = transcribe_with_azure(audio_file, text_file, log_file)
        elif backend == "whisper":
            uv = uv_bin()
            if not uv or not os.access(uv, os.X_OK):
                print("asr-recorder: uv is not installed or executable.", file=sys.stderr)
                returncode = 1
            else:
                cmd = [uv, "run", "--project", str(PROJECT_ROOT), "whisper", str(audio_file),
                       "--model", os.environ.get("S2T_WHISPER_MODEL", "tiny"),
                       "--output_dir", str(audio_file.parent), "--output_format", "txt"]
                with log_file.open("w", encoding="utf-8") as log:
                    returncode = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=False).returncode
        else:
            print(f"asr-recorder: unsupported S2T_ASR_BACKEND: {backend}", file=sys.stderr)
            returncode = 1
    except OSError as exc:
        print(f"asr-recorder: could not transcribe: {exc}", file=sys.stderr)
        notify("ASR Recorder", "Could not transcribe")
        clear_transcription_state(directory)
        return 1
    finally:
        signal_process(indicator_pid, signal.SIGTERM)

    if returncode != 0:
        print(f"asr-recorder: {backend} transcription failed. See {log_file}", file=sys.stderr)
        print_log_excerpt(log_file)
        notify("ASR Recorder", f"{backend.title()} transcription failed")
        clear_transcription_state(directory)
        return returncode

    if not text_file.exists():
        print(f"asr-recorder: transcription file was not created: {text_file}", file=sys.stderr)
        notify("ASR Recorder", "Whisper did not create a transcript")
        clear_transcription_state(directory)
        return 1

    copied = copy_to_clipboard(text_file)
    pasted = copied and paste_from_clipboard()
    if show_transcript_enabled():
        show_transcription(text_file)
    if pasted:
        notify("ASR Recorder", "Transcription pasted")
    elif copied:
        notify("ASR Recorder", "Transcription copied to clipboard")
    else:
        notify("ASR Recorder", f"Transcription saved: {text_file.name}")
    print(f"asr-recorder: transcribed {audio_file} -> {text_file}")
    clear_transcription_state(directory)
    return 0


def start_recording() -> int:
    directory = tmp_dir()
    with state_lock(directory):
        current = load_active_state(directory)
        if current and current.get("phase") == "recording":
            print(f"asr-recorder: already recording to {current.get('audio_file')}")
            return 0
        if current and current.get("phase") == "transcribing":
            print("asr-recorder: already transcribing.")
            return 0

        if not command_exists("ffmpeg"):
            print("asr-recorder: ffmpeg is not installed.", file=sys.stderr)
            return 1

        audio_file = timestamped_audio_path(directory)
        log_file = audio_file.with_suffix(".ffmpeg.log")
        backend = os.environ.get("S2T_AUDIO_BACKEND", "pulse")
        audio_input = os.environ.get("S2T_AUDIO_INPUT", "default")

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "warning",
            "-f",
            backend,
            "-i",
            audio_input,
            "-ar",
            "16000",
            "-ac",
            "1",
            "-y",
            str(audio_file),
        ]

        with log_file.open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )

        time.sleep(0.35)
        if proc.poll() is not None:
            print(f"asr-recorder: ffmpeg failed to start. See {log_file}", file=sys.stderr)
            print_log_excerpt(log_file)
            return 1

        indicator_pid = start_visible_indicator(audio_file)
        write_state(
            directory,
            {
                "phase": "recording",
                "ffmpeg_pid": proc.pid,
                "indicator_pid": indicator_pid,
                "audio_file": str(audio_file),
                "log_file": str(log_file),
                "started_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

        notify("ASR Recorder", f"Recording to {audio_file.name}")
        print(f"asr-recorder: recording to {audio_file}")
        return 0


def stop_recording() -> int:
    directory = tmp_dir()
    with state_lock(directory):
        current = load_active_state(directory)
        if not current:
            print("asr-recorder: no recording is running.", file=sys.stderr)
            return 1
        if current.get("phase") == "transcribing":
            print(f"asr-recorder: already transcribing {current.get('audio_file')}")
            return 0

        ffmpeg_pid = current.get("ffmpeg_pid")
        indicator_pid = current.get("indicator_pid")
        audio_file = Path(current["audio_file"])

        signal_process(indicator_pid, signal.SIGTERM)
        signal_process(ffmpeg_pid, signal.SIGINT)

        if not wait_for_exit(ffmpeg_pid, 5):
            signal_process(ffmpeg_pid, signal.SIGTERM)
            wait_for_exit(ffmpeg_pid, 2)

        signal_process(indicator_pid, signal.SIGTERM)
        clear_state(directory)

        if not audio_file.exists() or audio_file.stat().st_size == 0:
            print(f"asr-recorder: recording was not saved: {audio_file}", file=sys.stderr)
            return 1

        write_state(
            directory,
            {
                "phase": "transcribing",
                "transcriber_pid": os.getpid(),
                "audio_file": str(audio_file),
                "started_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        print(f"asr-recorder: saved {audio_file}")

    return transcribe_audio(audio_file, directory)


def status() -> int:
    directory = tmp_dir()
    with state_lock(directory):
        current = load_active_state(directory)
    if current and current.get("phase") == "recording":
        print(f"recording: {current.get('audio_file')}")
        return 0
    if current and current.get("phase") == "transcribing":
        print(f"transcribing: {current.get('audio_file')}")
        return 0
    print("idle")
    return 1


def toggle_recording() -> int:
    directory = tmp_dir()
    with state_lock(directory):
        current = load_active_state(directory)
    if current and current.get("phase") == "recording":
        return stop_recording()
    if current and current.get("phase") == "transcribing":
        print(f"asr-recorder: already transcribing {current.get('audio_file')}")
        return 0
    return start_recording()


def main(argv: list[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Start and stop a small ASR recorder.")
    parser.add_argument("command", choices=["start", "stop", "toggle", "status"])
    args = parser.parse_args(argv)

    if args.command == "start":
        return start_recording()
    if args.command == "stop":
        return stop_recording()
    if args.command == "toggle":
        return toggle_recording()
    if args.command == "status":
        return status()
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
