"""Default-id tool hits must attach to the active real call (War Room fix).

Real PSTN calls proved the gap live: ElevenLabs webhook tools don't know our
internal call ids, so every mid-call event landed on the LIVE_CALL_ID fallback
row while the War Room watched the real call's uuid and showed nothing.
"""
from app import db
from app.routers import tools

REAL_ID = "2a39a8b9-a824-4ec7-ad74-f4c89f66e7ce"


def test_default_id_resolves_to_active_real_call(monkeypatch):
    flipped = []
    monkeypatch.setattr(db, "available", lambda: True)
    monkeypatch.setattr(db, "get_active_real_call",
                        lambda: {"id": REAL_ID, "status": "ringing"})
    monkeypatch.setattr(db, "update_call_status",
                        lambda call_id, status: flipped.append((call_id, status)))
    assert tools._resolve_call_id(tools.LIVE_CALL_ID) == REAL_ID
    assert flipped == [(REAL_ID, "live")]  # ringing → live on first tool contact


def test_default_id_stays_when_no_active_call(monkeypatch):
    monkeypatch.setattr(db, "available", lambda: True)
    monkeypatch.setattr(db, "get_active_real_call", lambda: None)
    assert tools._resolve_call_id(tools.LIVE_CALL_ID) == tools.LIVE_CALL_ID
    assert tools._resolve_call_id(None) == tools.LIVE_CALL_ID


def test_explicit_call_id_passes_through(monkeypatch):
    monkeypatch.setattr(db, "get_active_real_call",
                        lambda: (_ for _ in ()).throw(AssertionError("must not look up")))
    assert tools._resolve_call_id(REAL_ID) == REAL_ID
