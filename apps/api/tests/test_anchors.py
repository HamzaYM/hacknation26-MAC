"""engine/anchors.py — BenchmarkReport builder + provenance.

Fixture backend (BENCHMARK_SOURCE default): assertions pin the exact anchor
methods, provenance fields, coverage statuses, RAND flags, Medicare multiples,
and the totals/ask surface — all derived from data/seed/benchmarks_v0.json via
the lookup layer, no invented numbers.
"""
import json

import pytest
from jsonschema import Draft7Validator

from app.config import REPO_ROOT, load_vertical
from app.engine.anchors import build_benchmark_report
from app.engine.lookup import FIXTURE_HOSPITAL, FixtureLookup
from app.models import JobSpec


def _spec(lines, **kw):
    return JobSpec.model_validate({
        "case_id": "c1", "patient": {},
        "insurance": {"payer_name": kw.get("payer"), "plan_type": kw.get("plan")},
        "bill": {"facility_name": kw.get("hospital", FIXTURE_HOSPITAL),
                 "account_number": "A1", "line_items": lines},
        "eob": {"line_items": []},
        "entities": [{"name": FIXTURE_HOSPITAL, "kind": "facility"}],
    })


@pytest.fixture(scope="module")
def schema():
    with open(REPO_ROOT / "contracts" / "anchor_set.schema.json") as f:
        return json.load(f)


def _report(lines, **kw):
    return build_benchmark_report(_spec(lines, **kw), FixtureLookup(), load_vertical())


def test_report_validates_against_contract(schema):
    rep = _report([{"cpt": "71046", "description": "CXR", "date_of_service": "2026-06-02",
                    "units": 1, "billed_amount": 412.0, "billing_entity": "facility"}])
    Draft7Validator(schema).validate(rep)


def test_every_anchor_carries_full_provenance():
    rep = _report([{"cpt": "71046", "date_of_service": "2026-06-02", "units": 1,
                    "billed_amount": 412.0, "billing_entity": "facility"}])
    anchors = rep["lines"][0]["anchors"]
    methods = {a["method"] for a in anchors}
    assert {"medicare", "rand_norm_estimate", "cross_payer_band", "cash_price"} <= methods
    for a in anchors:
        assert a["source"] and a["confidence"] in {"high", "medium", "estimated"} and a["label"]


def test_rand_norm_estimate_is_always_labeled_estimated():
    rep = _report([{"cpt": "71046", "date_of_service": "2026-06-02", "units": 1,
                    "billed_amount": 412.0, "billing_entity": "facility"}])
    rand = next(a for a in rep["lines"][0]["anchors"] if a["method"] == "rand_norm_estimate")
    assert rand["label"] == "estimated (RAND norm)"
    assert rand["confidence"] == "estimated"
    # 63.0 Medicare x 2.54 RAND norm = 160.02
    assert rand["value"] == 160.02


def test_medicare_multiple_fair_band_and_rand_flag():
    # 71046: Medicare 63.0; billed 412 → 6.54x; fair band 1.5x-2.5x = 94.5-157.5;
    # 412 > 2.54x63=160.02 → rand_flag; excess = 412 - 157.5 = 254.5
    rep = _report([{"cpt": "71046", "date_of_service": "2026-06-02", "units": 1,
                    "billed_amount": 412.0, "billing_entity": "facility"}])
    ln = rep["lines"][0]
    assert ln["medicare_multiple"] == 6.54
    assert ln["fair_band"]["low"] == 94.5 and ln["fair_band"]["high"] == 157.5
    assert ln["rand_flag"] is True
    assert ln["excess_above_band"] == 254.5


def test_units_scale_the_medicare_line_value():
    # 2 units of 96374 (Medicare 104.7): line Medicare = 209.4; billed 210 → 1.0x
    rep = _report([{"cpt": "96374", "date_of_service": "2026-06-02", "units": 2,
                    "billed_amount": 210.0, "billing_entity": "facility"}])
    ln = rep["lines"][0]
    assert ln["medicare_multiple"] == 1.0
    assert ln["fair_band"]["high"] == round(2.5 * 209.4, 2)


def test_coverage_absent_from_chargemaster_for_facility_standard_code():
    rep = _report([{"cpt": "99999", "date_of_service": "2026-06-02", "units": 1,
                    "billed_amount": 500.0, "billing_entity": "facility"}])
    assert rep["lines"][0]["coverage"] == "absent_from_chargemaster"


def test_coverage_professional_excluded_never_flags_professional():
    rep = _report([{"cpt": "99999", "date_of_service": "2026-06-02", "units": 1,
                    "billed_amount": 500.0, "billing_entity": "professional"}])
    assert rep["lines"][0]["coverage"] == "professional_excluded"


def test_totals_expose_multiples_and_ask_surface():
    # 71046 (Medicare 63) + 96374 (Medicare 104.7) = 167.7 Medicare total
    rep = _report([
        {"cpt": "71046", "date_of_service": "2026-06-02", "units": 1, "billed_amount": 200.0,
         "billing_entity": "facility"},
        {"cpt": "96374", "date_of_service": "2026-06-02", "units": 1, "billed_amount": 300.0,
         "billing_entity": "facility"},
    ])
    t = rep["totals"]
    assert t["billed"] == 500.0
    assert t["medicare"] == 167.7
    assert t["medicare_multiple"] == round(500.0 / 167.7, 2)
    assert t["ask_anchor"] == round(1.5 * 167.7, 2)   # self_pay_target_multiple_low
    assert t["ask_target"] == round(2.0 * 167.7, 2)   # self_pay_target_multiple_high
    assert t["floor"] == 167.7                          # Medicare is the hard floor


def test_data_version_pins_the_fixture_backend():
    rep = _report([{"cpt": "71046", "date_of_service": "2026-06-02", "units": 1,
                    "billed_amount": 100.0, "billing_entity": "facility"}])
    assert rep["data_version"]["chargemaster"] == "fixture:benchmarks_v0"
