"""Seed the demo case's recorded patient authorization.

Generates Maya's ~20s authorization clip with ElevenLabs TTS (Alex voice, a
female voice matching Maya's fiction; eleven_flash_v2) reading the exact
statement, then stores it THROUGH the product's own upload endpoint
(POST /cases/demo/authorization) so the demo case has a real on-file
authorization and the whole flow is exercised end to end.

The spoken statement is the SAME text persisted with the recording and read back
verbatim by the negotiator when a rep challenges authorization mid-call, so the
audio and the stored statement_text match exactly.

Usage:
    python scripts/seed_authorization.py                 # API on :8000
    API_BASE=http://localhost:8017 python scripts/seed_authorization.py

Requires ELEVENLABS_API_KEY in the root .env. Caches the generated mp3 at
data/demo_docs/maya_authorization.mp3 so re-runs don't re-bill TTS.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

# Alex — female voice, matches Maya's fiction (patient records her OWN voice).
VOICE_ID = "jTWqplUkOPQwOegNjhal"
MODEL_ID = "eleven_flash_v2"
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
CACHE = Path(__file__).resolve().parents[1] / "data" / "demo_docs" / "maya_authorization.mp3"

# Maya's details (apps/api/app/fixtures.py DEMO_JOB_SPEC). Kept in sync with the
# /confirm authorizationStatement() builder so the audio == the stored statement.
STATEMENT = (
    "My name is Maya Chen, date of birth March 14, 1995. "
    "This is regarding my account M G 4 4 7 1 9 8 3 at Mercy General Hospital. "
    "I authorize Haggl to discuss, negotiate, dispute, and adjust the charges and "
    "payment arrangements on this account on my behalf. "
    "This authorization is effective today and remains valid until I revoke it. "
    "You may reach me directly to confirm."
)


def generate_clip() -> bytes:
    if CACHE.exists() and CACHE.stat().st_size > 0:
        print(f"using cached clip: {CACHE} ({CACHE.stat().st_size} bytes)")
        return CACHE.read_bytes()
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        sys.exit("ELEVENLABS_API_KEY not set (root .env)")
    print(f"generating TTS ({MODEL_ID}, voice {VOICE_ID})…")
    resp = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": STATEMENT, "model_id": MODEL_ID,
              "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
        timeout=120,
    )
    resp.raise_for_status()
    audio = resp.content
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(audio)
    print(f"saved clip: {CACHE} ({len(audio)} bytes)")
    return audio


def upload(audio: bytes) -> None:
    print(f"uploading through {API_BASE}/cases/demo/authorization …")
    resp = httpx.post(
        f"{API_BASE}/cases/demo/authorization",
        files={"file": ("maya_authorization.mp3", audio, "audio/mpeg")},
        data={"statement": STATEMENT},
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    print("on_file:", body.get("on_file"))
    print("recorded_at:", body.get("recorded_at"))
    print("uploaded_to_bucket:", body.get("uploaded"))
    print("persisted_to_db:", body.get("persisted"))
    print("statement_text:", body.get("statement_text"))


if __name__ == "__main__":
    upload(generate_clip())
