"""Simulator sequence contracts — pure layer only (no DB, no sleeps).

Every scenario must satisfy the frozen War Room contract: a disclosure
tool_call, the expected quote arc, rungs from the REAL state machine, a
terminal outcome per persona, and the honesty audit as the LAST tool_call.
"""
import pytest

from app.fixtures_users import NINA_JOB_SPEC
from app.models import JobSpec
from app.simulator import (
    ENTITY_PERSONAS,
    SCENARIOS,
    build_generic_sequence,
    build_sequence,
    lever_event_name,
    load_entity_personas,
)


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


# ── identity retargeting + persona resolution (Findings 3 & 5) ─────────────
def _nina_entity(kind):
    return next(e for e in JobSpec.model_validate(NINA_JOB_SPEC).entities if e.kind == kind)


def _all_strings(steps):
    out = []
    for s in steps:
        if s["kind"] == "event":
            p = s["payload"]
            out += [str(v) for v in (p.get("text"), p.get("result")) if v]
        elif s["kind"] == "outcome":
            o = s["outcome"]
            out += [str(v) for v in (o.get("rep_name"), o.get("next_action")) if v]
            out += list((o.get("honesty_audit") or {}).get("checked_claims", []))
    return out


def test_nina_sim_speaks_nina_never_maya():
    """Finding 3: simulating Nina's case speaks HER identity, never Maya's."""
    entity = _nina_entity("anesthesia")
    steps = build_sequence("policy_citer", "sim-nina", spec=NINA_JOB_SPEC, entity=entity)
    blob = " | ".join(_all_strings(steps))
    assert "Maya" not in blob                                        # never another patient's name
    assert "Bay State Emergency Physicians" not in blob             # never another case's entity
    assert "Nina Osei" in blob                                      # speaks her own name
    assert "Commonwealth Anesthesia Associates" in blob            # her own counterparty
    # single-anchor scenario → the opening balance is Nina's own ($3,120), not $640
    assert [e["payload"]["amount"] for e in events(steps, "quote")] == [3120.0]


def test_nina_account_number_retargeted_never_mayas():
    """A script that voices an account number speaks Nina's, never MG-4471983."""
    entity = _nina_entity("facility")
    steps = build_sequence("gruff_stonewaller", "sim-nacct", spec=NINA_JOB_SPEC, entity=entity)
    blob = " | ".join(_all_strings(steps))
    assert "MG-4471983" not in blob and "Maya" not in blob
    assert "CAA-2026-8841" in blob and "Nina Osei" in blob


def test_missing_patient_data_falls_back_to_neutral_never_maya():
    """Finding 3c: a spec that can't fill a slot uses neutral phrasing, not Maya."""
    entity = _nina_entity("anesthesia")
    thin = {"case_id": "case-thin", "patient": {}, "bill": {}}
    steps = build_sequence("gruff_stonewaller", "sim-thin", spec=thin, entity=entity)
    blob = " | ".join(_all_strings(steps))
    assert "Maya" not in blob and "MG-4471983" not in blob
    assert "the patient" in blob and "this account" in blob


def test_unmapped_kind_falls_back_to_generic_persona_with_note():
    """Finding 3b: anesthesia (unmapped) → generic replay, noted on first status."""
    assert ENTITY_PERSONAS.get("anesthesia") == "policy_citer"  # was None (skipped) before
    entity = _nina_entity("anesthesia")
    steps = build_sequence("policy_citer", "sim-generic", spec=NINA_JOB_SPEC, entity=entity)
    first_status = next(s for s in steps if s["kind"] == "status")
    assert "generic negotiation replay" in first_status.get("note", "")
    assert "anesthesia" in first_status["note"]


def test_mapped_kind_has_no_generic_replay_note():
    entity = _nina_entity("facility")                          # facility IS mapped
    steps = build_sequence("gruff_stonewaller", "sim-fac", spec=NINA_JOB_SPEC, entity=entity)
    assert all("note" not in s for s in steps if s["kind"] == "status")


def test_maya_spec_leaves_scripts_untouched():
    """The default demo path (Maya) is byte-identical with or without her spec."""
    from app.fixtures import DEMO_JOB_SPEC

    entity = JobSpec.model_validate(DEMO_JOB_SPEC).entities[0]
    with_spec = build_sequence("gruff_stonewaller", "sim-x", spec=DEMO_JOB_SPEC, entity=entity)
    plain = build_sequence("gruff_stonewaller", "sim-x")
    assert _all_strings(with_spec) == _all_strings(plain)


def test_config_entity_persona_override_honored():
    """Finding 5: config simulator.entity_personas overrides the code defaults."""
    m = load_entity_personas({"simulator": {"entity_personas":
                                            {"facility": "human_facility_supervisor"}}})
    assert m.get("facility") == "human_facility_supervisor"    # config wins
    assert m.get("collections") == "collections_agent"         # code default preserved
    assert m.get("anesthesia") == "policy_citer"               # unmapped → generic fallback


def test_default_entity_personas_unchanged_by_shipped_config():
    """DEFAULT UNCHANGED: the shipped config keeps the demo mapping."""
    assert ENTITY_PERSONAS.get("facility") == "gruff_stonewaller"
    assert ENTITY_PERSONAS.get("er_physician_group") == "policy_citer"
    assert ENTITY_PERSONAS.get("collections") == "collections_agent"


class TestGenericCaseDriver:
    """build_generic_sequence / build_sequence's non-Maya dispatch —
    generalized pipeline, WS3. Uses Dan's fixture case (fixtures_users.py) as
    a real, non-Maya case with its own balance/entities/flags."""

    def test_deterministic_for_the_same_inputs(self):
        from app.fixtures_users import DAN_CASE_ID

        a = build_generic_sequence("sim-gen-1", DAN_CASE_ID)
        b = build_generic_sequence("sim-gen-1", DAN_CASE_ID)
        assert a == b

    def test_uses_the_case_own_numbers_not_maya(self):
        """Dan's collections balance is $2,140 (fixtures_users.py), not
        Maya's $4,287/$980 — the generic driver must speak Dan's numbers and
        Dan's own name, never Maya's literals."""
        from app.fixtures_users import DAN_CASE_ID

        steps = build_generic_sequence("sim-gen-2", DAN_CASE_ID)
        quotes = [s["payload"]["amount"] for s in steps
                 if s["kind"] == "event" and s["type"] == "quote"]
        assert quotes[0] == 2140.0
        transcript_text = " ".join(
            s["payload"]["text"] for s in steps
            if s["kind"] == "event" and s["type"] == "transcript")
        assert "Dan Kowalski" in transcript_text
        assert "Maya" not in transcript_text
        assert "4,287" not in transcript_text

    def test_ends_with_honesty_audit_and_one_outcome(self):
        from app.fixtures_users import DAN_CASE_ID

        steps = build_generic_sequence("sim-gen-3", DAN_CASE_ID)
        assert steps[0] == {"kind": "status", "status": "ringing"}
        assert steps[-1] == {"kind": "status", "status": "ended"}
        last_tool = [s for s in steps if s["kind"] == "event" and s["type"] == "tool_call"][-1]
        assert "honesty_audit" in last_tool["payload"]["name"]
        outcomes = [s for s in steps if s["kind"] == "outcome"]
        assert len(outcomes) == 1
        assert outcomes[0]["outcome"]["original_amount"] == 2140.0

    def test_build_sequence_dispatches_generic_for_non_demo_case(self):
        from app.fixtures_users import DAN_CASE_ID

        via_dispatch = build_sequence("collections_agent", "sim-gen-4", case_id=DAN_CASE_ID)
        direct = build_generic_sequence("sim-gen-4", DAN_CASE_ID)
        assert via_dispatch == direct

    def test_build_sequence_keeps_scripted_persona_for_demo_case_id(self):
        """Passing DEMO_CASE_ID explicitly must reproduce the exact
        hand-authored script — no behavior change for Maya's own launch."""
        from app.fixtures import DEMO_CASE_ID

        via_dispatch = build_sequence("gruff_stonewaller", "sim-gen-5", case_id=DEMO_CASE_ID)
        direct = SCENARIOS["gruff_stonewaller"]("sim-gen-5")
        assert via_dispatch == direct

    def test_build_sequence_omitted_case_id_unchanged(self):
        """The original two-arg call signature (no case_id) must be byte-for-byte
        identical to before this change — test_simulator.py's other tests all
        rely on this."""
        assert build_sequence("policy_citer", "sim-gen-6") == SCENARIOS["policy_citer"]("sim-gen-6")
