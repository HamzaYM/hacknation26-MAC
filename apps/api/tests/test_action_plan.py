"""Lever pack + action-plan assembler vs. data/seed/demo_answer_key.json.

The whole point of wiring J's config/levers.json + benchmarks into the action
plan is that every dollar figure, statute, and date the user sees is code-computed
and reconciled with the locked demo truth. These tests are that lock.
"""
import json

import pytest

from app.action_plan_copy import _verbatim_ok, generate_action_plan_copy
from app.config import SEED_DIR, load_vertical
from app.engine import levers
from app.engine.action_plan import build_action_plan_input
from app.engine.flags import detect_flags
from app.fixtures import demo_benchmarks

from fixtures import demo_job_spec


def _demo_payload() -> dict:
    return build_action_plan_input(
        demo_job_spec(),
        detect_flags(demo_job_spec(), load_vertical(), demo_benchmarks()),
        demo_benchmarks(), load_vertical(),
    )


@pytest.fixture(scope="module")
def answer_key() -> dict:
    with open(SEED_DIR / "demo_answer_key.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def flags():
    return detect_flags(demo_job_spec(), load_vertical(), demo_benchmarks())


@pytest.fixture(scope="module")
def totals():
    return {"medicare_total": 438.0, "mrf_cash_total": 2633.25, "mrf_negotiated_median_total": 999.30}


# ── lever pack ────────────────────────────────────────────────────────────────
def test_provider_route_arms_the_demo_lever_set(flags, totals):
    armed = levers.armed_levers(demo_job_spec(), flags, demo_benchmarks(), "provider", totals)
    assert [l["id"] for l in armed] == [
        "501r_charity_care", "501r_agb_limitation", "price_transparency_mrf",
        "medicare_benchmark", "duplicate_charge_dispute", "upcode_dispute", "unbundle_dispute",
    ]


def test_collections_route_arms_collections_levers(flags, totals):
    armed = levers.armed_levers(demo_job_spec(), flags, demo_benchmarks(), "collections", totals)
    assert {l["id"] for l in armed} == {"fdcpa_debt_validation", "credit_bureau_paid_removal"}


def test_citations_interpolate_answer_key_numbers(flags, totals):
    armed = {l["id"]: l["citation"] for l in
             levers.armed_levers(demo_job_spec(), flags, demo_benchmarks(), "provider", totals)}
    assert "$438.00" in armed["medicare_benchmark"]              # medicare_total
    assert "$2,633.25" in armed["price_transparency_mrf"]        # mrf_cash_total
    assert "$412.00" in armed["duplicate_charge_dispute"]        # duplicate impact
    assert "99285" in armed["upcode_dispute"] and "99283" in armed["upcode_dispute"]
    assert "$2,011.21" in armed["upcode_dispute"]                # upcode impact
    assert "$642.00" in armed["unbundle_dispute"]               # unbundle impact
    assert "${" not in "".join(armed.values())                  # no unfilled placeholders


# ── action-plan payload ───────────────────────────────────────────────────────
def test_payload_reconciles_with_answer_key(answer_key):
    p = build_action_plan_input(demo_job_spec(), None or
                                detect_flags(demo_job_spec(), load_vertical(), demo_benchmarks()),
                                demo_benchmarks(), load_vertical())
    assert p["balance"] == answer_key["case"]["patient_balance"] == 4287.0
    assert p["patient_first_name"] == "Maya"
    assert {f["type"] for f in p["flags"]} == {"duplicate", "upcode", "unbundle", "eob_mismatch"}
    impacts = {f["type"]: f["dollar_impact"] for f in p["flags"]}
    assert impacts["duplicate"] == 412.0 and impacts["upcode"] == 2011.21 and impacts["unbundle"] == 642.0


def test_savings_band_brackets_the_settlement(answer_key):
    """The demo settles at $1,650 paid; that must sit inside [target, cash] — i.e.
    the savings band [balance-cash, balance-target] must contain the achieved savings."""
    p = build_action_plan_input(demo_job_spec(),
                                detect_flags(demo_job_spec(), load_vertical(), demo_benchmarks()),
                                demo_benchmarks(), load_vertical())
    lo, hi = p["savings_estimate"]["low"], p["savings_estimate"]["high"]
    settlement = answer_key["negotiation_arc"]["settlement"]      # 1650
    achieved_savings = p["balance"] - settlement                 # 2637
    assert lo <= achieved_savings <= hi


def test_timeline_dates_are_computed_from_statement(answer_key):
    p = build_action_plan_input(demo_job_spec(),
                                detect_flags(demo_job_spec(), load_vertical(), demo_benchmarks()),
                                demo_benchmarks(), load_vertical())
    # 240-day FAP window + 365-day credit-reporting delay from the 2026-06-20 statement
    assert p["timeline"]["fap_deadline"] == "2027-02-15"
    assert p["timeline"]["credit_report_earliest"] == "2027-06-20"
    assert p["timeline"]["gfe_dispute_deadline"] is None          # insured patient


# ── copywriter honesty guard ──────────────────────────────────────────────────
def test_fallback_copy_is_honest():
    p = _demo_payload()
    copy = generate_action_plan_copy(p, use_llm=False)
    ok, leaked = _verbatim_ok(copy, p)
    assert ok, f"fallback copy leaked uncited figures: {leaked}"
    assert copy["_source"].startswith("fallback")


def test_guard_rejects_hallucinated_figure():
    p = _demo_payload()
    good = generate_action_plan_copy(p, use_llm=False)
    bad = dict(good, savings_line="Guaranteed savings of $9,999.99 today")
    assert not _verbatim_ok(bad, p)[0]
    assert "9999.99" in _verbatim_ok(bad, p)[1]
