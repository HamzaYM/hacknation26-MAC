"""Voice Picker backend — allowlist, resolution, and that the chosen voice_id
actually flows into both call-start payload shapes (no real calls placed)."""
import pytest
from fastapi.testclient import TestClient

from app import elevenlabs_calls
from app.main import app
from app.services import voice_prefs

ALEX = "jTWqplUkOPQwOegNjhal"
MORGAN = "Jui2x0OuMt9XBfF1tWIo"
RILEY = "saQ3GQHMonWJoYcm6AJJ"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_the_three_voices_are_allowlisted():
    assert set(voice_prefs.VOICES) == {ALEX, MORGAN, RILEY}
    assert voice_prefs.DEFAULT_VOICE_ID == ALEX
    assert voice_prefs.is_allowed(MORGAN)
    assert not voice_prefs.is_allowed("some-random-id")


def test_resolve_falls_back_to_default_without_a_choice():
    # No DB in tests, so nothing is persisted → default (Alex).
    assert voice_prefs.resolve_voice("demo") == ALEX


def test_set_voice_rejects_unknown_id():
    with pytest.raises(ValueError):
        voice_prefs.set_voice("demo", "not-a-real-voice")


def test_server_payload_carries_the_override():
    body = elevenlabs_calls.build_outbound_body("agent-1", "phone-1", "+15551234567", voice_id=RILEY)
    assert body["conversation_initiation_client_data"]["conversation_config_override"]["tts"]["voice_id"] == RILEY
    # No voice_id → no override block (agent's own default voice is used).
    plain = elevenlabs_calls.build_outbound_body("agent-1", "phone-1", "+15551234567")
    assert "conversation_initiation_client_data" not in plain


def test_initiation_client_data_uses_resolved_voice():
    data = voice_prefs.initiation_client_data("demo")
    assert data["conversation_config_override"]["tts"]["voice_id"] == ALEX  # default w/o DB


def test_get_voice_endpoint_defaults_to_alex(client):
    resp = client.get("/cases/demo/voice")
    assert resp.status_code == 200
    body = resp.json()
    assert body["voice_id"] == ALEX
    assert body["voice_label"] == "Alex"
    assert body["is_default"] is True
    assert body["persisted"] is False  # no DB in tests


def test_put_voice_endpoint_validates_and_echoes(client):
    ok = client.put("/cases/demo/voice", json={"voice_id": MORGAN})
    assert ok.status_code == 200
    assert ok.json()["voice_id"] == MORGAN
    assert ok.json()["voice_label"] == "Morgan"
    # persisted is False without a DB, and that's fine (client mirrors to localStorage).
    assert ok.json()["persisted"] is False

    bad = client.put("/cases/demo/voice", json={"voice_id": "bogus"})
    assert bad.status_code == 400
