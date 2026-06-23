#!/usr/bin/env python3
"""
Reads transcribed text, applies phrase expansions from phrases.json,
writes result back to the same file.
"""
import sys
import json
import re
from pathlib import Path

def expand(text: str, phrases: dict) -> str:
    # Sort longest phrases first so more specific matches win over partial ones
    for phrase, expansion in sorted(phrases.items(), key=lambda x: -len(x[0])):
        if phrase.startswith("_"):
            continue
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        text = pattern.sub(expansion, text)
    return text.strip()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: expand_phrases.py <transcription_file>", file=sys.stderr)
        sys.exit(1)

    transcript_path = Path(sys.argv[1])
    phrases_path = Path(__file__).parent / "phrases.json"

    if not phrases_path.exists():
        sys.exit(0)

    with open(phrases_path) as f:
        phrases = json.load(f)

    text = transcript_path.read_text().strip()
    expanded = expand(text, phrases)

    transcript_path.write_text(expanded + "\n")
    print(f"[phrases] '{text}' -> '{expanded}'")
