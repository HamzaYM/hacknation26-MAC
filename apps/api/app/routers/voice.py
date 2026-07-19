"""Voice-picker endpoints — read/write the per-case negotiator voice.

Mounted at /cases so the resource reads GET/PUT /cases/{case_id}/voice. Kept in
its own router (not folded into cases.py or calls.py) to stay out of the way of
the branch rewriting the call routers.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import voice_prefs

router = APIRouter()


class VoiceChoice(BaseModel):
    voice_id: str


@router.get("/{case_id}/voice")
def get_voice(case_id: str) -> dict:
    """Current voice for a case. `persisted` is False when it came from the
    default rather than the DB — the web client then trusts its localStorage
    mirror instead."""
    chosen = voice_prefs.get_voice(case_id)
    persisted = voice_prefs.is_allowed(chosen)
    voice_id = chosen if persisted else voice_prefs.DEFAULT_VOICE_ID
    return {
        "case_id": case_id,
        "voice_id": voice_id,
        "voice_label": voice_prefs.label_for(voice_id),
        "is_default": voice_id == voice_prefs.DEFAULT_VOICE_ID,
        "persisted": persisted,
    }


@router.put("/{case_id}/voice")
def put_voice(case_id: str, choice: VoiceChoice) -> dict:
    try:
        persisted = voice_prefs.set_voice(case_id, choice.voice_id)
    except ValueError as err:
        raise HTTPException(400, str(err))
    return {
        "case_id": case_id,
        "voice_id": choice.voice_id,
        "voice_label": voice_prefs.label_for(choice.voice_id),
        "persisted": persisted,
    }
