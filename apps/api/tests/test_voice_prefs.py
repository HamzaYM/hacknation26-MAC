"""Voice Picker backend — allowlist, resolution, and that the chosen voice_id
actually flows into both call-start payload shapes (no real calls placed)."""
import pytest
from fastapi.testclient import TestClient

from app import elevenlabs_calls
from app.main import app
from app.services import voice_prefs

ALEX = "jTWqplUkOPQwOegNjhal"
ADAM = "pNInz6obpgDQGcFmaJgB"
RILEY = "saQ3GQHMonWJoYcm6AJJ"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def hermetic_voice_store(monkeypatch):
    """Stub the voice-pref DB helpers with an in-memory dict. Without this,
    app.main's load_dotenv() finds the repo-root .env from a worktree (dotenv
    searches parent dirs), and these tests read AND WRITE the live Supabase —
    which is how a test run once persisted a voice pref onto the demo case."""
    store: dict[str, str] = {}
    monkeypatch.setattr(voice_prefs.db, "get_case_voice", store.get)
    monkeypatch.setattr(voice_prefs.db, "set_case_voice",
                        lambda case_id, voice_id, label=None: False)
    monkeypatch.setattr(voice_prefs.db, "ensure_demo_case", lambda: None)


def test_the_three_voices_are_allowlisted():
    assert set(voice_prefs.VOICES) == {ALEX, ADAM, RILEY}
    assert voice_prefs.DEFAULT_VOICE_ID == ALEX
    assert voice_prefs.is_allowed(ADAM)
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
    ok = client.put("/cases/demo/voice", json={"voice_id": ADAM})
    assert ok.status_code == 200
    assert ok.json()["voice_id"] == ADAM
    assert ok.json()["voice_label"] == "Adam"
    # persisted is False without a DB, and that's fine (client mirrors to localStorage).
    assert ok.json()["persisted"] is False

    bad = client.put("/cases/demo/voice", json={"voice_id": "bogus"})
    assert bad.status_code == 400
