"""501(r) account-age clock + MA Health Safety Net Medical Hardship charity path.

Two research-grounded features (IRS 501(r)(6) / 26 CFR 1.501(r)-6; MA HSN Medical
Hardship, no FPL ceiling). All additive: the frozen StrategyDossier contract gains
two OPTIONAL fields; the demo case's behavior is unchanged.
"""
import copy
import json
from datetime import date

import pytest

from app.config import REPO_ROOT, load_vertical
from app.engine.dossier import (
    COLLECTIONS_WINDOW_DAYS,
    _days_since,
    build_dossier,
    compute_501r_window,
)
from app.engine.levers import charity_lead_arming, hardship_pct_threshold
from app.engine.state_machine import LadderStateMachine
from app.fixtures import DEMO_JOB_SPEC, demo_benchmarks
from app.models import JobSpec

from fixtures import demo_job_spec

# The demo's "today" (Hamza's brief): statement 2026-06-20 → this date = day 28.
TODAY = date(2026, 7, 18)
STATEMENT = "2026-06-20"


def _spec_with(fpl, income, bill_amount, nonprofit=True) -> JobSpec:
    raw = copy.deepcopy(DEMO_JOB_SPEC)
    raw["financial_profile"]["fpl_percent"] = fpl
    raw["financial_profile"]["household_income"] = income
    raw["bill"]["nonprofit_status"] = nonprofit
    raw["bill"]["patient_balance"] = bill_amount
    raw["bill"]["total_billed"] = bill_amount
    return JobSpec.model_validate(raw)


def _dossier_for(spec: JobSpec, today: date = TODAY):
    return build_dossier(spec, [], demo_benchmarks(), load_vertical(),
                         entity=spec.entities[0], today=today)


# ── 1. Dossier date math (clamp negative / None) ──────────────────────────────
def test_days_since_none_when_no_statement_date():
    assert _days_since(None, TODAY) is None
    assert _days_since("", TODAY) is None


def test_days_since_unparseable_is_none():
    assert _days_since("not-a-date", TODAY) is None


def test_days_since_counts_whole_days():
    assert _days_since(STATEMENT, TODAY) == 28


def test_days_since_clamps_future_statement_to_zero():
    # statement dated AFTER today → never a negative account age
    assert _days_since("2026-08-01", TODAY) == 0


# ── 2. Window flag nonprofit gating ───────────────────────────────────────────
def test_window_true_for_nonprofit_inside_120_days():
    days, window = compute_501r_window(STATEMENT, True, TODAY)
    assert days == 28 and window is True


def test_window_false_for_nonprofit_past_120_days():
    days, window = compute_501r_window("2026-01-01", True, TODAY)
    assert days == 198 and window is False


def test_window_none_for_forprofit_even_inside_120_days():
    # days still counted (facility-agnostic); the window flag is nonprofit-only
    days, window = compute_501r_window(STATEMENT, False, TODAY)
    assert days == 28 and window is None


def test_window_none_when_no_statement_date():
    assert compute_501r_window(None, True, TODAY) == (None, None)


def test_demo_case_dossier_is_open_day_28_of_120():
    """The exact demo values Hamza asked to verify: window OPEN, day 28 of 120."""
    dossier = _dossier_for(demo_job_spec())
    assert dossier.days_since_first_statement == 28
    assert dossier.inside_501r_window is True


# ── 3. Hardship arming matrix (4 cases) ───────────────────────────────────────
CHARITY_CFG = load_vertical()["thresholds"]["charity_lead"]


@pytest.mark.parametrize("fpl, income, bill, expected, why", [
    (250, 39000, 4287, True, "flat FPL gate (Maya): 250 <= 400"),
    (500, 60000, 30000, True, "hardship: 30000 >= 30% of 60000 (18000)"),
    (500, 60000, 5000, False, "hardship fails: 5000 < 30% of 60000 (18000)"),
    (700, 50000, 25000, True, "above-605 bracket: 25000 >= 40% of 50000 (20000)"),
])
def test_charity_lead_arming_matrix(fpl, income, bill, expected, why):
    armed, _reason = charity_lead_arming(CHARITY_CFG, fpl, income, bill)
    assert armed is expected, why


def test_hardship_bracket_thresholds():
    brackets = CHARITY_CFG["medical_hardship"]["min_expense_pct_of_income"]
    assert hardship_pct_threshold(300, brackets) == 20
    assert hardship_pct_threshold(400, brackets) == 25
    assert hardship_pct_threshold(600, brackets) == 30
    assert hardship_pct_threshold(700, brackets) == 40
    assert hardship_pct_threshold(None, brackets) is None


def test_maya_still_arms_statutory_via_flat_gate():
    """DO NOT change demo behavior: Maya (250% FPL) still arms the charity lever."""
    ids = [lv.id for lv in _dossier_for(demo_job_spec()).levers]
    assert "statutory_501r" in ids


def test_high_fpl_large_bill_arms_via_hardship():
    ids = [lv.id for lv in _dossier_for(_spec_with(500, 60000, 30000)).levers]
    assert "statutory_501r" in ids


def test_high_fpl_small_bill_does_not_arm():
    ids = [lv.id for lv in _dossier_for(_spec_with(500, 60000, 5000)).levers]
    assert "statutory_501r" not in ids


def test_high_fpl_large_bill_forprofit_does_not_arm():
    """Hardship is a nonprofit obligation — a for-profit facility never arms it."""
    ids = [lv.id for lv in _dossier_for(_spec_with(500, 60000, 30000, nonprofit=False)).levers]
    assert "statutory_501r" not in ids


# ── 4. Collections-threat pushback note + compact fact (state machine) ─────────
@pytest.fixture
def machine():
    return LadderStateMachine(load_vertical())


@pytest.fixture
def open_dossier():
    return _dossier_for(demo_job_spec())  # inside_501r_window True, day 28


def test_compact_501r_fact_surfaced_once_early(machine, open_dossier):
    machine.ensure_call("c1", open_dossier)
    first = machine.advance("c1", "open_and_hold_account", "accepted")
    assert "501(r) window: day 28 of 120" in first["notes"]
    assert "charity application window open (240 days)" in first["notes"]
    # ONCE early: the fact does not repeat on the next advance
    second = machine.advance("c1", "reach_authority", "accepted")
    assert "501(r) window" not in second["notes"]


def test_collections_threat_arms_flat_pushback_inside_window(machine, open_dossier):
    machine.ensure_call("c2", open_dossier)
    resp = machine.advance("c2", "line_item_disputes", "rejected",
                           quote="If you don't pay we'll send you to collections.")
    assert "120-day window" in resp["notes"]
    assert "26 CFR 1.501(r)-6" in resp["notes"]
    # flat + factual, never menacing
    assert "no menace" in resp["notes"]


def test_no_501r_notes_when_window_closed_or_forprofit(machine):
    """A for-profit account (inside_501r_window None) gets neither the fact nor the
    pushback, even on a collections threat."""
    forprofit = _dossier_for(_spec_with(250, 39000, 4287, nonprofit=False))
    assert forprofit.inside_501r_window is None
    machine.ensure_call("c3", forprofit)
    resp = machine.advance("c3", "line_item_disputes", "rejected",
                           quote="We'll send you to collections.")
    assert "501(r)" not in resp["notes"]
    assert "120-day window" not in resp["notes"]


# ── 5. Contract additive check ────────────────────────────────────────────────
def test_schema_additions_are_additive_only():
    with open(REPO_ROOT / "contracts" / "strategy_dossier.schema.json") as f:
        schema = json.load(f)
    props = schema["properties"]
    # the two new optional fields exist and allow null
    for field in ("days_since_first_statement", "inside_501r_window"):
        assert field in props
        assert "null" in props[field]["type"]
        assert field not in schema["required"]
    # existing required list is untouched (contract frozen — additive only)
    assert schema["required"] == [
        "case_id", "target_entity", "route", "levers", "anchor", "target", "floor",
    ]


def test_window_constant_is_120():
    assert COLLECTIONS_WINDOW_DAYS == 120
