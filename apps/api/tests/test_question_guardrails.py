"""Question guardrails (A1–A6): coverage gate, already-asked memory, question
repeat cap, and the end_call_summary hard gate (soft-fail). No DB — db.* helpers
are no-ops here, so these exercise the deterministic engine + router logic."""
import copy

import pytest
from fastapi.testclient import TestClient

from app.config import load_vertical
from app.engine.state_machine import LadderStateMachine
from app.fixtures import demo_dossier
from app.main import app

OPEN_TAGS = {"account_hold_requested", "itemized_bill_status", "rep_name_captured"}


# ── state machine (A1 coverage gate, A2 already-asked, A3 repeat cap) ───────
@pytest.fixture
def machine():
    return LadderStateMachine(load_vertical())


@pytest.fixture
def call(machine):
    machine.ensure_call("q-1", demo_dossier())
    return "q-1"


def test_gate_dormant_without_questions_asked(machine, call):
    """Legacy callers never send tags → gate never engages (protects the 100)."""
    resp = machine.advance(call, "open_and_hold_account", "accepted")
    assert resp["move_allowed"] is True
    assert resp["next_move"] == "reach_authority"
    assert "coverage_incomplete" not in resp


def test_gate_blocks_first_time_when_tags_missing(machine, call):
    resp = machine.advance(call, "open_and_hold_account", "accepted",
                           questions_asked=["rep_name_captured"])
    assert resp["move_allowed"] is False
    assert resp["next_move"] == "open_and_hold_account"  # stays on the rung
    assert "before moving on, cover:" in resp["notes"]
    assert "itemized bill status" in resp["notes"]      # humanized tag
    assert "account hold requested" in resp["notes"]


def test_gate_allows_second_time_and_flags_incomplete(machine, call):
    machine.advance(call, "open_and_hold_account", "accepted",
                    questions_asked=["rep_name_captured"])
    resp = machine.advance(call, "open_and_hold_account", "accepted")
    assert resp["move_allowed"] is True
    assert resp["next_move"] == "reach_authority"       # advanced this time
    assert set(resp["coverage_incomplete"]) == {"account_hold_requested", "itemized_bill_status"}


def test_full_coverage_advances_clean(machine, call):
    resp = machine.advance(call, "open_and_hold_account", "accepted",
                           questions_asked=list(OPEN_TAGS))
    assert resp["move_allowed"] is True
    assert resp["next_move"] == "reach_authority"
    assert "coverage_incomplete" not in resp


def test_already_asked_flags_repeat_of_covered_tag(machine, call):
    machine.advance(call, "open_and_hold_account", "accepted", questions_asked=list(OPEN_TAGS))
    resp = machine.advance(call, "reach_authority", "accepted",
                           questions_asked=["rep_name_captured"])
    assert resp["already_asked"] == ["rep_name_captured"]
    assert "reference the earlier answer" in resp["notes"]


def test_question_repeat_cap_after_three_in_a_row(machine, call):
    # same tag reported three advances running, across different levers so the
    # (separate) lever-repetition cap doesn't fire instead
    machine.advance(call, "reach_authority", "rejected", questions_asked=["interest_accruing"])
    machine.advance(call, "line_item_disputes", "partial", questions_asked=["interest_accruing"])
    resp = machine.advance(call, "benchmark_anchor", "partial", questions_asked=["interest_accruing"])
    assert resp.get("question_repeat_cap") == ["interest_accruing"]
    assert "log it unresolved" in resp["notes"]


def test_collections_diagnostic_questions_is_gated(machine):
    dossier = copy.deepcopy(demo_dossier())
    dossier.route = "collections"
    machine.ensure_call("q-c", dossier)
    resp = machine.advance("q-c", "diagnostic_questions", "accepted",
                           questions_asked=["interest_accruing"])
    assert resp["move_allowed"] is False
    assert "before moving on, cover:" in resp["notes"]


# ── end_call_summary gates (A4/A5/A6) via the router ───────────────────────
@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_end_call_summary_rejects_gated_win_missing_fields(client):
    resp = client.post("/tools/end_call_summary", json={
        "call_id": "ecs-1", "outcome_type": "reduction", "final_amount": 1650.0,
        "original_amount": 4287.0, "reference_number": "MG-2247",
        "written_confirmation": True,  # isolate A4 from A5
        # rep_name + agreed_action deliberately missing
    })
    body = resp.json()
    assert body["received"] is False
    assert set(body["missing"]) == {"rep_name", "agreed_action"}
    assert "before hanging up" in body["say"]


def test_end_call_summary_accepts_incomplete_on_second_attempt(client):
    resp = client.post("/tools/end_call_summary", json={
        "call_id": "ecs-2", "outcome_type": "reduction", "final_amount": 1650.0,
        "original_amount": 4287.0, "reference_number": "MG-2247",
        "written_confirmation": True, "confirm_incomplete": True,
    })
    body = resp.json()
    assert body["received"] is True
    assert set(body["missing_fields"]) == {"rep_name", "agreed_action"}


def test_written_confirmation_downgrades_to_callback(client):
    resp = client.post("/tools/end_call_summary", json={
        "call_id": "ecs-3", "outcome_type": "reduction", "final_amount": 876.0,
        "original_amount": 4287.0, "reference_number": "MG-2247",
        "rep_name": "Dana", "agreed_action": "adjust to 876",
        # no written_confirmation → A5 downgrade
    })
    body = resp.json()
    assert body["received"] is True
    assert body["outcome_downgraded"] == "callback"


def test_written_confirmation_kept_and_marked_with_confirm_incomplete(client):
    resp = client.post("/tools/end_call_summary", json={
        "call_id": "ecs-4", "outcome_type": "reduction", "final_amount": 876.0,
        "original_amount": 4287.0, "reference_number": "MG-2247",
        "rep_name": "Dana", "agreed_action": "adjust to 876", "confirm_incomplete": True,
    })
    body = resp.json()
    assert body["received"] is True
    assert body["written_confirmation_pending"] is True
    assert "outcome_downgraded" not in body


def test_reference_number_unverified_warning_without_read_back(client):
    resp = client.post("/tools/end_call_summary", json={
        "call_id": "ecs-5", "outcome_type": "reduction", "final_amount": 876.0,
        "original_amount": 4287.0, "reference_number": "MG-2247",
        "rep_name": "Dana", "agreed_action": "adjust", "written_confirmation": True,
    })
    assert "reference_number_unverified" in resp.json().get("warnings", [])


def test_documented_decline_stays_ungated(client):
    resp = client.post("/tools/end_call_summary", json={
        "call_id": "ecs-6", "outcome_type": "documented_decline"})
    body = resp.json()
    assert body["received"] is True
    assert "missing" not in body


def test_report_lever_result_surfaces_coverage_incomplete(client):
    r1 = client.post("/tools/report_lever_result", json={
        "call_id": "qg-endpoint", "lever": "open_and_hold_account", "result": "accepted",
        "questions_asked": ["rep_name_captured"]})
    assert r1.json()["move_allowed"] is False
    r2 = client.post("/tools/report_lever_result", json={
        "call_id": "qg-endpoint", "lever": "open_and_hold_account", "result": "accepted"})
    assert set(r2.json()["coverage_incomplete"]) == {"account_hold_requested", "itemized_bill_status"}
