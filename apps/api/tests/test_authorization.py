"""Recorded patient authorization — endpoint, mid-call tool, trigger arming, honesty.

Maya records her authorization on the platform; the agent presents it (reads it
verbatim) when a rep challenges authorization mid-call. There is NO native
ElevenLabs way to play a stored clip into a live PSTN call, so the tool relays the
exact recorded words and the agent offers to send the recording + written release.

Tool-gated honesty: the tool returns statement_text ONLY when a recording is on
file (on_file true); it never invents one.
"""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import load_vertical
from app.engine.state_machine import LadderStateMachine
from app.fixtures import DEMO_CASE_ID, demo_dossier
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_authorization():
    """Isolate the in-process authorization cache between tests (module global)."""
    with db._lock:
        db._authorization_overrides.clear()
    yield
    with db._lock:
        db._authorization_overrides.clear()


STATEMENT = (
    "My name is Maya Chen, date of birth March 14th, 1995. This is about my account "
    "M G dash 4 4 7 1 9 8 3 at Mercy General Hospital. I authorize Haggl to discuss, "
    "negotiate, dispute, and adjust the charges and payment arrangements on this account "
    "on my behalf. This is effective today and stays valid until I revoke it. You can "
    "reach me directly to confirm."
)


# ── endpoint: upload + get ────────────────────────────────────────────────
class TestEndpoint:
    def test_upload_then_get_reports_on_file(self, client):
        resp = client.post(
            "/cases/demo/authorization",
            files={"file": ("auth.webm", b"FAKEWEBMBYTES", "audio/webm")},
            data={"statement": STATEMENT},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["on_file"] is True
        assert body["statement_text"] == STATEMENT
        assert body["recorded_at"] is not None

        got = client.get("/cases/demo/authorization")
        assert got.status_code == 200
        assert got.json()["on_file"] is True
        assert got.json()["statement_text"] == STATEMENT

    def test_get_before_any_recording_is_off_file(self, client, monkeypatch):
        # Hermetic: the live DB (found via dotenv parent-dir discovery) now has
        # Maya's seeded authorization; stub the lookup to the empty state.
        from app import db
        monkeypatch.setattr(db, "get_case_authorization", lambda cid: None)
        monkeypatch.setattr(db, "_authorization_fallback", {}, raising=False)
        resp = client.get("/cases/demo/authorization")
        assert resp.status_code == 200
        body = resp.json()
        assert body["on_file"] is False
        assert body["statement_text"] is None
        assert body["recording_url"] is None

    def test_upload_rejects_empty_statement(self, client):
        resp = client.post(
            "/cases/demo/authorization",
            files={"file": ("auth.webm", b"BYTES", "audio/webm")},
            data={"statement": "   "},
        )
        assert resp.status_code == 400

    def test_upload_rejects_empty_recording(self, client):
        resp = client.post(
            "/cases/demo/authorization",
            files={"file": ("auth.webm", b"", "audio/webm")},
            data={"statement": STATEMENT},
        )
        assert resp.status_code == 400

    def test_upload_unknown_case_404s(self, client):
        resp = client.post(
            "/cases/nope/authorization",
            files={"file": ("auth.webm", b"BYTES", "audio/webm")},
            data={"statement": STATEMENT},
        )
        assert resp.status_code == 404


# ── mid-call tool: get_authorization ──────────────────────────────────────
class TestTool:
    def test_tool_off_file_returns_no_statement(self, client, monkeypatch):
        """Honesty: nothing recorded → on_file false, NO statement text, and an
        instruction not to invent one."""
        from app import db
        monkeypatch.setattr(db, "get_case_authorization", lambda cid: None)
        monkeypatch.setattr(db, "_authorization_fallback", {}, raising=False)
        resp = client.post("/tools/get_authorization", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["on_file"] is False
        assert "statement_text" not in body
        assert "do not claim" in body["say"].lower()

    def test_tool_on_file_returns_verbatim_statement(self, client):
        client.post(
            "/cases/demo/authorization",
            files={"file": ("auth.webm", b"BYTES", "audio/webm")},
            data={"statement": STATEMENT},
        )
        resp = client.post("/tools/get_authorization", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["on_file"] is True
        assert body["statement_text"] == STATEMENT      # verbatim, unchanged
        assert body["patient_name"] == "Maya Chen"
        assert body["reference"] == "MG-4471983"
        # It must instruct the agent NOT to claim it plays audio.
        assert "cannot play" in body["playback_note"].lower() or \
               "can't play" in body["playback_note"].lower() or \
               "cannot play the audio" in body["playback_note"].lower()


# ── trigger-phrase arming (state machine) ─────────────────────────────────
class TestArming:
    @pytest.fixture
    def machine(self):
        m = LadderStateMachine(load_vertical())
        m.ensure_call("auth-call", demo_dossier())
        return m

    def test_authorization_challenge_arms_the_move(self, machine):
        resp = machine.advance(
            "auth-call", "open_and_hold_account", "stonewalled",
            quote="Wait, do you even have authorization to discuss this account?",
        )
        assert "authorization challenged" in resp["notes"]
        assert "verbatim" in resp["notes"]

    def test_hipaa_phrase_arms_the_move(self, machine):
        resp = machine.advance(
            "auth-call", "open_and_hold_account", "stonewalled",
            quote="That's a HIPAA issue, I can't discuss this with you.",
        )
        assert "authorization challenged" in resp["notes"]

    def test_arms_only_once_per_call(self, machine):
        first = machine.advance(
            "auth-call", "open_and_hold_account", "stonewalled",
            quote="Do you have authorization on file?",
        )
        assert "authorization challenged" in first["notes"]
        second = machine.advance(
            "auth-call", "line_item_disputes", "stonewalled",
            quote="Again, I need to verify identity here.",
        )
        assert "authorization challenged" not in (second.get("notes") or "")

    def test_unrelated_quote_does_not_arm(self, machine):
        resp = machine.advance(
            "auth-call", "open_and_hold_account", "rejected",
            quote="We don't negotiate balances here.",
        )
        assert "authorization challenged" not in (resp.get("notes") or "")


# ── honesty audit allows the recorded-authorization numbers (D3) ───────────
class TestAuditAllowsAuthorizationNumbers:
    """When the case has a recorded authorization, the agent reads Maya's recorded
    statement VERBATIM if a rep challenges authority. Those spoken numbers (DOB
    year, account digits) are legitimate quotes of an on-file record, so
    _allowed_numbers_for_call folds them into the allowed set and the honest
    read-back passes D3 rather than flagging as uncited."""

    STMT = (
        "My name is Maya Chen, date of birth March 14, 1995. This is about my account "
        "M G 4 4 7 1 9 8 3 at Mercy General Hospital. I authorize Haggl to discuss, "
        "negotiate, dispute, and adjust the charges on this account on my behalf."
    )

    def test_statement_year_is_added_to_allowed(self, monkeypatch):
        from app.routers import webhooks
        monkeypatch.setattr(webhooks.db, "get_case_authorization",
                            lambda cid: {"authorization_path": "x",
                                         "authorization_statement": self.STMT})
        allowed = webhooks._allowed_numbers_for_call()
        assert 1995.0 in allowed

    def test_quoting_seeded_statement_passes_d3(self, monkeypatch):
        from app.engine.honesty import audit_call
        from app.routers import webhooks
        monkeypatch.setattr(webhooks.db, "get_case_authorization",
                            lambda cid: {"authorization_path": "x",
                                         "authorization_statement": self.STMT})
        allowed = webhooks._allowed_numbers_for_call()
        transcript = [
            {"speaker": "rep", "text": "Do you have authorization on file?"},
            {"speaker": "agent", "text": "I do. Her recorded words were: " + self.STMT},
        ]
        result = audit_call(transcript, allowed, disclosure_mode="only_if_asked")
        assert result["checks"]["numbers"]["passed"] is True
        assert result["passed"] is True

    def test_without_authorization_the_year_is_not_allowed(self, monkeypatch):
        """Guard: absent a recorded authorization, the statement's numbers are NOT
        silently citable (the allowance is scoped to an on-file record)."""
        from app.routers import webhooks
        monkeypatch.setattr(webhooks.db, "get_case_authorization", lambda cid: None)
        allowed = webhooks._allowed_numbers_for_call()
        assert 1995.0 not in allowed
