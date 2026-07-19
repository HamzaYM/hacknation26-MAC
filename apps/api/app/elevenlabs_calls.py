"""ElevenLabs outbound calling — FEATURE-FLAGGED STUB.

⚠ UNTESTED against the live API: real outbound calls need Twilio numbers
imported into ElevenLabs (provisioning H0/H1, blocked on Hamza). Until then
the flag stays off and callers get {"enabled": False} without dialing.

Enable with ELEVENLABS_OUTBOUND_ENABLED=1 once numbers exist, then wire
POST /calls/launch to call outbound_call() instead of the simulator.
"""
from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("negotiator.elevenlabs")

OUTBOUND_URL = "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"


def enabled() -> bool:
    return os.environ.get("ELEVENLABS_OUTBOUND_ENABLED", "").lower() in ("1", "true")


def outbound_call(agent_id: str, agent_phone_number_id: str, to_number: str) -> dict:
    """Start a native-Twilio outbound call from an ElevenLabs agent.

    Returns the API response ({"conversation_id": ..., "callSid": ...} per docs)
    with "enabled": True, or {"enabled": False} when the feature flag is off.
    """
    if not enabled():
        return {"enabled": False,
                "note": "set ELEVENLABS_OUTBOUND_ENABLED=1 after Twilio numbers are provisioned"}
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return {"enabled": False, "note": "ELEVENLABS_API_KEY missing"}
    resp = httpx.post(
        OUTBOUND_URL,
        headers={"xi-api-key": api_key},
        json={
            "agent_id": agent_id,
            "agent_phone_number_id": agent_phone_number_id,
            "to_number": to_number,
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    log.info("outbound call started: %s", body)
    return {"enabled": True, **body}
