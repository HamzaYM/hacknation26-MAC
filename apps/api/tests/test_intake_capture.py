"""Intake transcript parser + the webhook path that persists its answers.

The parser is deterministic and conservative: a field is emitted only when the
agent's question is classified AND the following patient turn carries a number.
The webhook routes an intake-agent post-call payload to that parser and lands the
result on the case (matched by agent_id or an 'intake' agent name).
"""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.fixtures import DEMO_CASE_ID
from app.fixtures_users import spec_for_case
from app.intake_capture import parse_financial_answers
from app.main import app


@pytest.fixture(autouse=True)
def _fixture_only(monkeypatch):
    monkeypatch.setattr(db, "_get_conn", lambda: None)
    db._financial_overrides.clear()
    yield
    db._financial_overrides.clear()


@pytest.fixture()
def client():
    return TestClient(app)


# ── parser unit tests ─────────────────────────────────────────────────────
def test_parses_all_four_fields():
    transcript = [
        {"role": "agent", "message": "Great. How much could you comfortably put down today?"},
        {"role": "user", "message": "Maybe about $2,500."},
        {"role": "agent", "message": "And the most you could comfortably pay each month?"},
        {"role": "user", "message": "Around 200 dollars a month."},
        {"role": "agent", "message": "What's your household income a year, roughly?"},
        {"role": "user", "message": "About 42,000."},
        {"role": "agent", "message": "And how many people are in your household?"},
        {"role": "user", "message": "Two."},
    ]
    assert parse_financial_answers(transcript) == {
        "lump_sum_available": 2500.0,
        "max_monthly_payment": 200.0,
        "household_income": 42000.0,
        "household_size": 2,
    }


def test_handles_spoken_number_words():
    transcript = [
        {"role": "agent", "message": "How much could you put down today?"},
        {"role": "user", "message": "About two thousand five hundred dollars."},
    ]
    assert parse_financial_answers(transcript) == {"lump_sum_available": 2500.0}


def test_normalized_speaker_text_shape_also_works():
    transcript = [
        {"speaker": "agent", "text": "What could you put down today, as a lump sum?"},
        {"speaker": "rep", "text": "I could do 1700."},
    ]
    assert parse_financial_answers(transcript) == {"lump_sum_available": 1700.0}


def test_conservative_when_no_clear_question():
    """No classifiable question → nothing captured, even with numbers present."""
    transcript = [
        {"role": "agent", "message": "Thanks for confirming your name and date of birth."},
        {"role": "user", "message": "Yes, that's 12 34 my address."},
    ]
    assert parse_financial_answers(transcript) == {}


def test_last_amount_after_the_question_wins():
    transcript = [
        {"role": "agent", "message": "How much could you put down today?"},
        {"role": "user", "message": "Hmm, maybe 1000."},
        {"role": "user", "message": "Actually, I could do 1500."},
    ]
    assert parse_financial_answers(transcript) == {"lump_sum_available": 1500.0}


# ── webhook integration ───────────────────────────────────────────────────
def _intake_envelope(**data_extra):
    return {
        "type": "post_call_transcription",
        "data": {
            "conversation_id": "conv_intake_1",
            "transcript": [
                {"role": "agent", "message": "How much could you put down today?"},
                {"role": "user", "message": "About $2,500."},
                {"role": "agent", "message": "How many people are in your household?"},
                {"role": "user", "message": "Two."},
            ],
            **data_extra,
        },
    }


def test_webhook_captures_intake_by_agent_name(client):
    env = _intake_envelope(agent_id="agent_x", metadata={"agent_name": "Intake Interview"})
    resp = client.post("/webhooks/elevenlabs", json=env)
    assert resp.status_code == 200
    assert resp.json()["intake"] is True
    assert db._financial_overrides[DEMO_CASE_ID] == {
        "lump_sum_available": 2500.0, "household_size": 2,
    }
    # and it overlays onto the served spec
    assert spec_for_case("demo")["financial_profile"]["lump_sum_available"] == 2500.0


def test_webhook_captures_intake_by_agent_id(client, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_AGENT_ID_INTAKE", "agent_intake_007")
    env = _intake_envelope(agent_id="agent_intake_007")
    assert client.post("/webhooks/elevenlabs", json=env).json()["intake"] is True
    assert db._financial_overrides[DEMO_CASE_ID]["lump_sum_available"] == 2500.0


def test_webhook_routes_to_metadata_case_id(client):
    env = _intake_envelope(metadata={"agent_name": "intake", "case_id": DEMO_CASE_ID})
    client.post("/webhooks/elevenlabs", json=env)
    assert DEMO_CASE_ID in db._financial_overrides


def test_non_intake_conversation_is_not_captured(client):
    """A negotiator payload (no intake id / name) falls through unchanged — no
    financial capture, and no matching call so call_found is False."""
    env = _intake_envelope(agent_id="agent_negotiator", metadata={"agent_name": "Adam"})
    body = client.post("/webhooks/elevenlabs", json=env).json()
    assert body.get("intake") is None
    assert body["call_found"] is False
    assert db._financial_overrides == {}
