"""Simulator sequence contracts — pure layer only (no DB, no sleeps).

Every scenario must satisfy the frozen War Room contract: a disclosure
tool_call, the expected quote arc, rungs from the REAL state machine, a
terminal outcome per persona, and the honesty audit as the LAST tool_call.
"""
import pytest

from app.simulator import SCENARIOS, build_sequence, lever_event_name


def events(steps, type_):
    return [s for s in steps if s["kind"] == "event" and s["type"] == type_]


def tool_names(steps):
    return [e["payload"]["name"] for e in events(steps, "tool_call")]


def step_index(steps, pred):
    return next(i for i, s in enumerate(steps) if pred(s))


ARCS = {
    "gruff_stonewaller": ([4287.0], "documented_decline"),
    "policy_citer": ([640.0], "charity_app_initiated"),
    "collections_agent": ([980.0, 833.0, 294.0, 490.0, 392.0], "reduction"),
    "human_facility_supervisor": ([4287.0, 3875.0, 2400.0, 1650.0], "reduction"),
}


def test_arcs_cover_every_scenario():
    assert set(ARCS) == set(SCENARIOS)


@pytest.mark.parametrize("persona", sorted(ARCS))
def test_scenario_contract(persona):
    steps = build_sequence(persona, f"sim-{persona}")
    expected_quotes, expected_outcome = ARCS[persona]

    # status lifecycle: queued row → ringing → live → ended
    assert [s["status"] for s in steps if s["kind"] == "status"] == ["ringing", "live", "ended"]

    # ≥1 disclosure tool_call (War Room token: name contains "disclose")
    assert any("disclose" in n for n in tool_names(steps))

    # quote arc — every number spoken, in order, payload {"amount": <number>}
    assert [e["payload"]["amount"] for e in events(steps, "quote")] == expected_quotes

    # transcript payload shape {"speaker": "agent"|"rep", "text": str}
    for e in events(steps, "transcript"):
        assert e["payload"]["speaker"] in ("agent", "rep") and e["payload"]["text"]

    # state changes come from the real ladder: {"rung": str, "rung_index": int}, nondecreasing
    rungs = events(steps, "state_change")
    assert rungs
    indices = [e["payload"]["rung_index"] for e in rungs]
    assert indices == sorted(indices)
    assert all(isinstance(e["payload"]["rung"], str) for e in rungs)

    # honesty audit is the LAST tool_call and its result contains "passed"
    last_tool = events(steps, "tool_call")[-1]["payload"]
    assert "honesty_audit" in last_tool["name"]
    assert "passed" in last_tool["result"]

    # exactly one terminal outcome, staged before the ended status flip
    outcome_steps = [s for s in steps if s["kind"] == "outcome"]
    assert len(outcome_steps) == 1
    assert outcome_steps[0]["outcome"]["outcome_type"] == expected_outcome
    assert steps.index(outcome_steps[0]) < step_index(
        steps, lambda s: s["kind"] == "status" and s["status"] == "ended")


def test_stonewaller_ends_in_documented_decline_with_callback():
    steps = build_sequence("gruff_stonewaller", "sim-sw")
    assert events(steps, "escalation")  # stonewall forced reach_authority
    outcome = [s for s in steps if s["kind"] == "outcome"][0]["outcome"]
    assert outcome["next_action"] == "callback"
    assert outcome["final_amount"] is None


def test_policy_citer_501r_unlocks_charity_app():
    steps = build_sequence("policy_citer", "sim-pc")
    assert "lever_armed:charity_care" in tool_names(steps)
    outcome = [s for s in steps if s["kind"] == "outcome"][0]["outcome"]
    assert outcome["winning_lever"] == "statutory_501r"
    assert outcome["reference_number"] == "BSEP-FA-1102"


def test_collections_settles_at_40_pct():
    steps = build_sequence("collections_agent", "sim-col")
    outcome = [s for s in steps if s["kind"] == "outcome"][0]["outcome"]
    assert outcome["original_amount"] == 980.0
    assert outcome["final_amount"] == 392.0
    assert outcome["reduction_pct"] == 60.0


def test_human_supervisor_levers_precede_each_move():
    steps = build_sequence("human_facility_supervisor", "sim-hs")

    def tool_at(name):
        return step_index(steps, lambda s: s["kind"] == "event" and s["type"] == "tool_call"
                          and name in s["payload"]["name"])

    def quote_at(amount):
        return step_index(steps, lambda s: s["kind"] == "event" and s["type"] == "quote"
                          and s["payload"]["amount"] == amount)

    assert tool_at("duplicate_charge") < quote_at(3875.0)
    assert tool_at("benchmark_anchor") < quote_at(2400.0)
    assert tool_at("lump_sum_settlement") < quote_at(1650.0)
    # settling at 1650 is above the dossier target → the engine demands escalation
    assert events(steps, "escalation")
    outcome = [s for s in steps if s["kind"] == "outcome"][0]["outcome"]
    assert outcome["reference_number"] == "MG-ADJ-2247"
    assert outcome["reduction_pct"] == 61.5


def test_lever_event_name_mapping():
    assert lever_event_name("error_duplicate_71046") == "lever_armed:duplicate_charge"
    assert lever_event_name("benchmark_anchor") == "lever_armed:benchmark_anchor"
    assert lever_event_name("statutory_501r") == "lever_armed:charity_care"
    assert lever_event_name("statutory_nsa") == "lever_armed:nsa"
    assert lever_event_name("error_unbundle_80053") == "lever_armed:error_unbundle_80053"
