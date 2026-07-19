"""Per-case voice preference — the Voice Picker's backend, kept in one place.

Deliberately isolated (its own module + a tiny router) so it rebases cleanly
against the branch rewriting routers/calls.py. The voice is applied at call
INITIATION via conversation_config_override, never by PATCHing the shared agent
(a PATCH races when several calls run at once).

Persistence is best-effort: app/db.py no-ops without a DB or before migration
0002 is applied, so resolve_voice() always returns a usable voice_id and the web
UI keeps working from its localStorage mirror.
"""
from __future__ import annotations

from .. import db
from ..fixtures import DEMO_CASE_ID

# The three cloned voices in our ElevenLabs workspace. This is an allowlist:
# only these voice_ids are ever accepted from a client or injected into a call,
# so a bad value can never reach the outbound-call payload.
VOICES: dict[str, str] = {
    "jTWqplUkOPQwOegNjhal": "Alex",    # warm and polite — default
    "Jui2x0OuMt9XBfF1tWIo": "Morgan",  # calm and analytical
    "saQ3GQHMonWJoYcm6AJJ": "Riley",   # firm and direct
}

DEFAULT_VOICE_ID = "jTWqplUkOPQwOegNjhal"  # Alex


def is_allowed(voice_id: str | None) -> bool:
    return voice_id in VOICES


def label_for(voice_id: str) -> str | None:
    return VOICES.get(voice_id)


def normalize_case_id(case_id: str) -> str:
    """Map the "demo" alias to the fixture UUID; pass real UUIDs through."""
    return DEMO_CASE_ID if case_id in ("demo", DEMO_CASE_ID) else case_id


def get_voice(case_id: str) -> str | None:
    """The persisted voice for a case, or None when unset / no DB / table absent."""
    return db.get_case_voice(normalize_case_id(case_id))


def set_voice(case_id: str, voice_id: str) -> bool:
    """Persist a chosen voice. Returns True only when it actually hit the DB.

    Raises ValueError for a voice_id outside the allowlist (the router turns this
    into a 400). A False return is fine and expected: the web client mirrors the
    choice to localStorage, so the UI is correct even when nothing persisted.
    """
    if not is_allowed(voice_id):
        raise ValueError(f"unknown voice_id: {voice_id!r}")
    cid = normalize_case_id(case_id)
    if cid == DEMO_CASE_ID:
        db.ensure_demo_case()  # make the FK resolve for the only case that exists today
    return db.set_case_voice(cid, voice_id, label_for(voice_id))


def resolve_voice(case_id: str) -> str:
    """The voice to actually use on a call: the chosen one, else the default."""
    chosen = get_voice(case_id)
    return chosen if is_allowed(chosen) else DEFAULT_VOICE_ID


def conversation_config_override(voice_id: str) -> dict:
    """The override block that swaps the agent's voice for ONE conversation."""
    return {"tts": {"voice_id": voice_id}}


def initiation_client_data(case_id: str) -> dict:
    """`conversation_initiation_client_data` for a server-placed outbound call,
    carrying the resolved voice as a per-call override (no agent PATCH)."""
    return {"conversation_config_override": conversation_config_override(resolve_voice(case_id))}
