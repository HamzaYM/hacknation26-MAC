"""ElevenLabs post-call webhook → transcript events + recording storage.

Best-effort by design: verifies the HMAC signature only when
ELEVENLABS_WEBHOOK_SECRET is set, matches the call by
elevenlabs_conversation_id, stores transcript turns as call_events, uploads
audio to the recordings bucket, and marks the call ended. Never raises back
at ElevenLabs. TODO(Hamza): OpenAI structured extraction → CallOutcome +
honesty verifier once real calls exist (simulated calls stage outcomes
directly via the simulator/tools).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os

import httpx
from fastapi import APIRouter, Request

from .. import db

router = APIRouter()
log = logging.getLogger("negotiator.webhooks")


def _signature_ok(raw: bytes, header: str | None) -> bool:
    """ElevenLabs-Signature: t=<unix ts>,v0=HMAC_SHA256(secret, "<t>.<body>")."""
    secret = os.environ.get("ELEVENLABS_WEBHOOK_SECRET", "")
    if not secret:
        return True  # graceful until the secret is provisioned
    if not header:
        return False
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts, sig = parts.get("t"), parts.get("v0")
    if not ts or not sig:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.{raw.decode()}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def _store_recording(call_id: str, audio: bytes) -> str | None:
    """Upload to the recordings bucket via the Storage REST API (service key)."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (url and key):
        return None
    path = f"{call_id}.mp3"
    try:
        resp = httpx.post(
            f"{url}/storage/v1/object/recordings/{path}",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "audio/mpeg",
                     "x-upsert": "true"},
            content=audio,
            timeout=60,
        )
        if resp.status_code in (200, 201):
            return f"recordings/{path}"
        log.warning("recording upload failed: %s %s", resp.status_code, resp.text[:200])
    except httpx.HTTPError as err:
        log.warning("recording upload failed: %s", err)
    return None


@router.post("/elevenlabs")
async def elevenlabs_post_call(request: Request) -> dict:
    raw = await request.body()
    if not _signature_ok(raw, request.headers.get("elevenlabs-signature")):
        return {"received": False, "error": "bad signature"}
    try:
        envelope = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return {"received": False, "error": "invalid json"}
    if not isinstance(envelope, dict):
        return {"received": False, "error": "unexpected payload"}

    wtype = envelope.get("type", "")
    data = envelope.get("data") or {}
    conversation_id = data.get("conversation_id")
    call = db.get_call_by_conversation(conversation_id) if conversation_id else None
    if call is None:
        return {"received": True, "type": wtype, "call_found": False}

    call_id = str(call["id"])
    if wtype == "post_call_transcription":
        for turn in data.get("transcript") or []:
            text = turn.get("message")
            if not text:
                continue
            speaker = "agent" if turn.get("role") == "agent" else "rep"
            db.insert_event(call_id, "transcript", {"speaker": speaker, "text": text})
        db.update_call_status(call_id, "ended")
    elif wtype == "post_call_audio":
        audio_b64 = data.get("full_audio")
        if audio_b64:
            try:
                path = _store_recording(call_id, base64.b64decode(audio_b64))
            except (ValueError, TypeError):
                path = None
            if path:
                db.set_call_recording(call_id, path)
    return {"received": True, "type": wtype, "call_found": True}
