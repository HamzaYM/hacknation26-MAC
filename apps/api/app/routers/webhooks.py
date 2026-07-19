"""ElevenLabs post-call webhook → transcript events + recording storage + honesty audit.

Best-effort by design: verifies the HMAC signature only when
ELEVENLABS_WEBHOOK_SECRET is set, matches the call by
elevenlabs_conversation_id, stores transcript turns as call_events, uploads
audio to the recordings bucket, runs the deterministic honesty audit against
the transcript, and marks the call ended. Never raises back at ElevenLabs.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Request

from .. import db, storage
from ..engine.honesty import audit_call
from ..fixtures import demo_benchmarks, demo_dossier

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
        transcript = []
        for turn in data.get("transcript") or []:
            text = turn.get("message")
            if not text:
                continue
            speaker = "agent" if turn.get("role") == "agent" else "rep"
            db.insert_event(call_id, "transcript", {"speaker": speaker, "text": text})
            transcript.append({"speaker": speaker, "text": text})
        # Run deterministic honesty audit on the transcript
        if transcript:
            _run_honesty_audit(call_id, transcript)
        db.update_call_status(call_id, "ended")
    elif wtype == "post_call_audio":
        audio_b64 = data.get("full_audio")
        if audio_b64:
            try:
                # storage.store_recording normalizes the /rest/v1-suffixed
                # SUPABASE_URL — the old local uploader didn't, so audio 404'd
                path = storage.store_recording(call_id, base64.b64decode(audio_b64))
            except (ValueError, TypeError):
                path = None
            if path:
                db.set_call_recording(call_id, path)
    return {"received": True, "type": wtype, "call_found": True}


def _allowed_numbers_for_call() -> list[float]:
    """Build the set of numbers the agent is allowed to speak.

    Sources: benchmarks (Medicare/cash/negotiated for each CPT), dossier
    (anchor/target/floor), case data (balance, EOB, FPL%), and CPT codes
    themselves (agent must cite codes by number).
    """
    nums: list[float] = []
    # Case-level locked numbers
    nums.extend([8432, 4287, 3875, 1700, 250])  # billed, balance, EOB, lump-sum, FPL%
    # CPT codes (agent cites these as bare numbers)
    for cpt in demo_benchmarks().keys():
        try:
            nums.append(float(cpt))
        except ValueError:
            pass
    # Benchmarks per CPT
    for row in demo_benchmarks().values():
        for key in ("medicare", "mrf_cash", "mrf_negotiated_median"):
            v = row.get(key)
            if v is not None:
                nums.append(float(v))
    # Dossier anchors
    dossier = demo_dossier()
    nums.extend([dossier.anchor, dossier.target, dossier.floor])
    # Flag dollar impacts (the agent cites these)
    from ..fixtures import demo_flags
    for f in demo_flags():
        nums.append(f.dollar_impact)
    return nums


def _run_honesty_audit(call_id: str, transcript: list[dict]) -> None:
    """Compute and persist the honesty audit for a completed call."""
    try:
        allowed = _allowed_numbers_for_call()
        result = audit_call(transcript, allowed)
        # Store as a honesty_audit event (visible in War Room)
        db.insert_event(call_id, "tool_call", {
            "name": "honesty_audit",
            "result": "passed" if result["passed"] else "FAILED",
            "detail": result,
        })
        log.info("honesty audit %s: %s", call_id, "passed" if result["passed"] else "FAILED")
    except Exception:  # noqa: BLE001 — never fail the webhook
        log.exception("honesty audit failed for %s", call_id)
