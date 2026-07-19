"""Ladder state machine: linear advance, stonewall → reach_authority,
hangup → documented_decline, floor/target enforcement."""
import pytest

from app.config import load_vertical
from app.engine.state_machine import LadderStateMachine
from app.fixtures import demo_dossier

PROVIDER_LADDER = load_vertical()["ladder"]["provider"]


@pytest.fixture
def machine():
    return LadderStateMachine(load_vertical())


@pytest.fixture
def call(machine):
    machine.ensure_call("call-1", demo_dossier())
    return "call-1"


def test_linear_advance_walks_the_provider_ladder(machine, call):
    resp = machine.advance(call, "open_and_hold_account", "accepted")
    assert resp["next_move"] == "reach_authority" and resp["move_allowed"]
    resp = machine.advance(call, "reach_authority", "accepted")
    assert resp["next_move"] == "financial_assistance_screen"
    assert machine.current_rung(call) == {
        "rung": "financial_assistance_screen", "rung_index": 2, "terminal": False, "outcome_type": None,
    }


def test_advance_clamps_at_the_last_rung(machine, call):
    last = PROVIDER_LADDER[-1]
    resp = machine.advance(call, last, "rejected")
    assert resp["next_move"] == last  # escalate_or_exit


def test_stonewalled_result_forces_reach_authority(machine, call):
    machine.advance(call, "open_and_hold_account", "accepted")
    machine.advance(call, "reach_authority", "accepted")
    machine.advance(call, "financial_assistance_screen", "accepted")
    resp = machine.advance(call, "line_item_disputes", "stonewalled")
    assert resp["next_move"] == "reach_authority"
    assert resp["escalation"] is True


def test_stonewall_trigger_phrase_in_quote_forces_reach_authority(machine, call):
    resp = machine.advance(call, "line_item_disputes", "rejected",
                           quote="Sir, THAT'S OUR POLICY, there is nothing to discuss.")
    assert resp["next_move"] == "reach_authority"
    assert resp["escalation"] is True


def test_stonewall_trigger_with_unicode_apostrophe(machine, call):
    """LLMs often produce curly quotes (\u2019) — must still match triggers."""
    resp = machine.advance(call, "line_item_disputes", "rejected",
                           quote="That\u2019s our policy, there\u2019s nothing I can do.")
    assert resp["next_move"] == "reach_authority"
    assert resp["escalation"] is True


def test_hangup_yields_terminal_documented_decline(machine, call):
    resp = machine.advance(call, "line_item_disputes", "hangup")
    assert resp["next_move"] == "documented_decline"
    assert resp["terminal"] is True
    assert resp["outcome_type"] == "documented_decline"
    assert resp["next_action"] == "callback"
    # terminal state is sticky
    resp = machine.advance(call, "benchmark_anchor", "accepted")
    assert resp["move_allowed"] is False
    assert machine.current_rung(call)["terminal"] is True


def test_floor_enforced_offer_above_1700_is_rejected(machine, call):
    before = machine.current_rung(call)["rung_index"]
    resp = machine.advance(call, "lump_sum_settlement", "partial", offer_amount=1800.00)
    assert resp["move_allowed"] is False
    assert "floor" in resp["notes"]
    assert machine.current_rung(call)["rung_index"] == before  # rung unchanged


def test_settling_above_target_requires_escalation_flag(machine, call):
    # $1,650 (the demo settlement) is ≤ floor $1,700 but > target $876
    resp = machine.advance(call, "lump_sum_settlement", "accepted", offer_amount=1650.00)
    assert resp["move_allowed"] is True
    assert resp["escalation_required"] is True


def test_offer_at_or_below_target_is_clean(machine, call):
    resp = machine.advance(call, "benchmark_anchor", "partial", offer_amount=876.00)
    assert resp["move_allowed"] is True
    assert "escalation_required" not in resp


def test_collections_route_walks_the_collections_ladder(machine):
    import copy

    dossier = copy.deepcopy(demo_dossier())
    dossier.route = "collections"
    machine.ensure_call("call-c", dossier)
    resp = machine.advance("call-c", "diagnostic_questions", "accepted")
    assert resp["next_move"] == "debt_validation_posture"


def test_stonewall_escalation_capped_at_two(machine, call):
    machine.advance(call, "line_item_disputes", "stonewalled")
    machine.advance(call, "reach_authority", "stonewalled")
    resp = machine.advance(call, "reach_authority", "stonewalled")
    assert resp["next_move"] == PROVIDER_LADDER[-1]  # escalate_or_exit
    assert "escalation limit" in resp["notes"]


def test_repetition_guardrail_forces_next_rung_after_three_identical_reports(machine, call):
    machine.advance(call, "line_item_disputes", "rejected")
    machine.advance(call, "line_item_disputes", "rejected")
    resp = machine.advance(call, "line_item_disputes", "rejected")
    assert resp.get("repetition_cap") is True
    assert "three times" in resp["notes"]
    # and the ladder moved on rather than re-arguing the same rung
    assert resp["next_move"] != "line_item_disputes"


def test_repetition_guardrail_ignores_accepted_results(machine, call):
    machine.advance(call, "open_and_hold_account", "accepted")
    machine.advance(call, "open_and_hold_account", "accepted")
    resp = machine.advance(call, "open_and_hold_account", "accepted")
    assert resp.get("repetition_cap") is None
