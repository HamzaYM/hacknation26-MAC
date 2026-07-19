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


def test_single_stonewall_advances_without_escalation_or_park(machine, call):
    """Escalation is last-resort now: ONE stonewall neither jumps to reach_authority
    nor parks — the agent may rephrase once, so the ladder just advances."""
    machine.advance(call, "open_and_hold_account", "accepted")
    machine.advance(call, "reach_authority", "accepted")
    machine.advance(call, "financial_assistance_screen", "accepted")
    resp = machine.advance(call, "line_item_disputes", "stonewalled")
    assert resp["next_move"] != "reach_authority"
    assert "escalation" not in resp
    assert "parked" not in resp


def test_second_stonewall_on_same_lever_parks_and_advances(machine, call):
    """Two unhedged stonewalls on the same lever = impasse → PARK it as an open item
    and move to the next lever (was: forced reach_authority)."""
    machine.advance(call, "line_item_disputes", "stonewalled")
    resp = machine.advance(call, "line_item_disputes", "stonewalled")
    assert resp["parked"] == {
        "lever": "line_item_disputes",
        "reason": "stonewalled twice on the same point — unhedged refusal",
    }
    assert resp["next_move"] != "line_item_disputes"      # advanced past the parked rung
    assert "escalation" not in resp                       # parked, not escalated
    assert machine.parked_topics(call) == [resp["parked"]]


def test_stonewall_trigger_phrase_parks_after_two(machine, call):
    """A config stonewall phrase ('that's our policy') is a stonewall signal; the
    same lever hitting it twice parks the topic instead of jumping to a supervisor."""
    machine.advance(call, "line_item_disputes", "rejected",
                    quote="Sir, THAT'S OUR POLICY, there is nothing to discuss.")
    resp = machine.advance(call, "line_item_disputes", "rejected",
                           quote="Again, that's our policy.")
    assert resp["parked"]["lever"] == "line_item_disputes"
    assert "escalation" not in resp


def test_stonewall_trigger_with_unicode_apostrophe_parks(machine, call):
    """LLMs often produce curly quotes — the trigger must still match, so two such
    quotes on a lever park it."""
    q = "That\u2019s our policy, there\u2019s nothing I can do."
    machine.advance(call, "line_item_disputes", "rejected", quote=q)
    resp = machine.advance(call, "line_item_disputes", "rejected", quote=q)
    assert resp["parked"]["lever"] == "line_item_disputes"


def test_hedged_refusal_does_not_park(machine, call):
    """A temporary/hedged refusal ('right now') is not a hard impasse — even twice on
    the same lever it must NOT park (the door is still open)."""
    machine.advance(call, "line_item_disputes", "stonewalled",
                    quote="I can't do that right now.")
    resp = machine.advance(call, "line_item_disputes", "stonewalled",
                           quote="Not right now, sorry.")
    assert "parked" not in resp
    assert machine.parked_topics(call) == []


def test_authority_quote_arms_reach_authority(machine, call):
    """(b) The rep says only someone with authority can act -> escalate now, even
    though a bare stonewall would only park."""
    resp = machine.advance(call, "line_item_disputes", "rejected",
                           quote="I'm sorry, I don't have the authority to adjust that.")
    assert resp["next_move"] == "reach_authority"
    assert resp["escalation"] is True


def test_escalation_arms_after_exhaustion(machine, call):
    """(a) Once every other lever is attempted or parked with material still open,
    the next non-accepted report arms reach_authority as the last resort."""
    for lever in ("line_item_disputes", "benchmark_anchor"):
        machine.advance(call, lever, "stonewalled")
        machine.advance(call, lever, "stonewalled")  # parks each
    for lever in ("open_and_hold_account", "financial_assistance_screen",
                  "self_pay_prompt_pay_ask", "lump_sum_settlement", "payment_plan_fallback"):
        machine.advance(call, lever, "rejected")
    resp = machine.advance(call, "payment_plan_fallback", "rejected")
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
    """The 2-escalation cap survives the last-resort rewrite: a third arming (via
    authority quotes) closes out at escalate_or_exit rather than looping supervisors."""
    q = "I don't have the authority to do that."
    machine.advance(call, "line_item_disputes", "rejected", quote=q)   # escalation 1
    machine.advance(call, "benchmark_anchor", "rejected", quote=q)     # escalation 2
    resp = machine.advance(call, "self_pay_prompt_pay_ask", "rejected", quote=q)  # 3rd → cap
    assert resp["next_move"] == PROVIDER_LADDER[-1]  # escalate_or_exit
    assert "escalation limit" in resp["notes"]


def test_repetition_signal_parks_the_topic(machine, call):
    """The same non-accepted point made three times in a row is an impasse: PARK it
    as an open item and advance (was: force-advance with repetition_cap)."""
    machine.advance(call, "line_item_disputes", "rejected")
    machine.advance(call, "line_item_disputes", "rejected")
    resp = machine.advance(call, "line_item_disputes", "rejected")
    assert resp["parked"]["lever"] == "line_item_disputes"
    assert "open item" in resp["notes"]
    # and the ladder moved on rather than re-arguing the same rung
    assert resp["next_move"] != "line_item_disputes"


def test_repetition_signal_ignores_accepted_results(machine, call):
    machine.advance(call, "open_and_hold_account", "accepted")
    machine.advance(call, "open_and_hold_account", "accepted")
    resp = machine.advance(call, "open_and_hold_account", "accepted")
    assert "parked" not in resp
