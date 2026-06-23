#!/usr/bin/env python3
import sys
from faster_whisper import WhisperModel

audio_path = sys.argv[1]
out_path = sys.argv[2]

model = WhisperModel("tiny", device="cpu", compute_type="int8")
segments, _ = model.transcribe(audio_path, language="en", condition_on_previous_text=False)

text = " ".join(seg.text.strip() for seg in segments)
with open(out_path, "w") as f:
    f.write(text)
