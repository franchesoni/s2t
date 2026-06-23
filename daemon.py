#!/usr/bin/env python3
"""S2T warm daemon — holds Whisper tiny model in RAM, serves transcription over HTTP on 127.0.0.1:7979."""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from faster_whisper import WhisperModel

PORT = 7979
model = None


def load_model():
    global model
    print("Loading Whisper tiny model...", flush=True)
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    print(f"Model ready. Listening on 127.0.0.1:{PORT}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/transcribe":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            audio_path = body.get("path", "")
            if not Path(audio_path).exists():
                self._respond(400, {"error": f"file not found: {audio_path}"})
                return
            segments, _ = model.transcribe(
                audio_path, language="en", condition_on_previous_text=False
            )
            text = " ".join(seg.text.strip() for seg in segments)
            self._respond(200, {"text": text})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    load_model()
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Daemon stopped.")
