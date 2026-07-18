"""Dossier builder vs. data/seed/demo_answer_key.json.

The arithmetic (all inputs from benchmarks_v0.json + medical_bills.yaml):
  corrected CPT set  bill codes with the upcode mapped 99285→99283 and the
                     unbundled components mapped →80053, deduped, benchmark-
                     covered only = {99283, 71046, 80053, 85025, 96374}
                     (== the answer key's demo_cpt_list)
  Medicare total     245 + 63 + 14.5 + 10.8 + 104.7            = $438.00
  anchor             1.5 × 438 (self_pay_target_multiple_low)  = $657.00
  high ask           2.0 × 438 (self_pay_target_multiple_high) = $876.00
  MRF cash total     1050 + 260 + 95 + 60 + 425                = $1,890.00
  target             min(1890, 876)                            = $876.00
  floor              financial_profile.lump_sum_available      = $1,700.00
So anchor ≤ target ≤ floor: open at 657, aim to settle ≤ 876, never pay >1700.
"""
import json

import pytest

from app.config import SEED_DIR, load_vertical
from app.engine.dossier import build_dossier, corrected_cpt_set
from app.engine.flags import detect_flags
from app.fixtures import demo_benchmarks, demo_dossier

from fixtures import demo_job_spec


@pytest.fixture(scope="module")
def answer_key() -> dict:
    with open(SEED_DIR / "demo_answer_key.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def dossier():
    return demo_dossier()


def test_corrected_cpt_set_matches_answer_key(answer_key):
    spec = demo_job_spec()
    flags = detect_flags(spec, load_vertical(), demo_benchmarks())
    assert corrected_cpt_set(spec, flags, demo_benchmarks()) == set(answer_key["demo_cpt_list"])


def test_anchor_target_floor_reconcile_with_answer_key(answer_key, dossier):
    low, high = answer_key["expected_totals"]["self_pay_band_150_200pct"]
    assert dossier.anchor == low == 657.00
    assert dossier.target == high == 876.00          # min(MRF cash 1890, 2.0×438=876)
    assert dossier.target < answer_key["expected_totals"]["mrf_cash_total"] == 1890.00
    assert dossier.floor == 1700.00                  # lump_sum_available
    assert dossier.anchor <= dossier.target <= dossier.floor


def test_route_and_target_entity(dossier):
    assert dossier.route == "provider"
    assert dossier.target_entity == "Mercy General Hospital"


def test_collections_route_for_collections_entity():
    spec = demo_job_spec()
    flags = detect_flags(spec, load_vertical(), demo_benchmarks())
    collections_entity = next(e for e in spec.entities if e.kind == "collections")
    d = build_dossier(spec, flags, demo_benchmarks(), load_vertical(), entity=collections_entity)
    assert d.route == "collections"
    assert d.target_entity == "Meridian Recovery Services"


def test_levers_armed_in_ladder_order(dossier):
    """Ladder order: financial_assistance_screen (statutory, charity FIRST) →
    line_item_disputes (one lever per flag) → benchmark_anchor."""
    assert [lv.id for lv in dossier.levers] == [
        "statutory_501r",            # nonprofit + fpl 250 ≤ 400
        "error_duplicate_71046",
        "error_upcode_99285",
        "error_unbundle_80053",
        "error_eob_mismatch",
        "benchmark_anchor",          # always armed when benchmarks exist
    ]
    assert all(lv.armed for lv in dossier.levers)


def test_error_lever_asks_equal_flag_impacts(dossier):
    asks = {lv.id: lv.dollar_ask for lv in dossier.levers}
    assert asks["error_duplicate_71046"] == 412.00
    assert asks["error_upcode_99285"] == 890.00
    assert asks["error_unbundle_80053"] == 642.00
    assert asks["error_eob_mismatch"] == 412.00
    assert asks["benchmark_anchor"] == 657.00


def test_citations_cover_every_corrected_cpt(answer_key, dossier):
    for cpt in answer_key["demo_cpt_list"]:
        assert any(f"CPT {cpt}" in c for c in dossier.citations), f"no citation for {cpt}"
