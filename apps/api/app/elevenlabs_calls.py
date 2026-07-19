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


def build_outbound_body(agent_id: str, agent_phone_number_id: str, to_number: str,
                        voice_id: str | None = None,
                        conversation_initiation_client_data: dict | None = None) -> dict:
    """The outbound-call request body. conversation_initiation_client_data
    carries per-call dynamic_variables (patient name, account, anchor/target —
    scripts/place_test_call.py shape). When voice_id is set, the chosen voice
    rides along in that same block as a per-call override
    (conversation_config_override.tts.voice_id) — the agent itself is never
    PATCHed, so concurrent calls each get their own voice without racing.
    """
    body: dict = {
        "agent_id": agent_id,
        "agent_phone_number_id": agent_phone_number_id,
        "to_number": to_number,
    }
    init_data = dict(conversation_initiation_client_data or {})
    if voice_id:
        init_data.setdefault("conversation_config_override", {}).setdefault("tts", {})["voice_id"] = voice_id
    if init_data:
        body["conversation_initiation_client_data"] = init_data
    return body


def outbound_call(agent_id: str, agent_phone_number_id: str, to_number: str,
                  conversation_initiation_client_data: dict | None = None,
                  voice_id: str | None = None) -> dict:
    """Start a native-Twilio outbound call from an ElevenLabs agent.

    conversation_initiation_client_data carries per-call dynamic_variables
    (patient name, account, anchor/target — scripts/place_test_call.py shape).
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
        json=build_outbound_body(agent_id, agent_phone_number_id, to_number,
                                 voice_id=voice_id,
                                 conversation_initiation_client_data=conversation_initiation_client_data),
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    log.info("outbound call started: %s", body)
    return {"enabled": True, **body}
