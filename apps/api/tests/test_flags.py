"""Red-flag engine vs. data/seed/demo_answer_key.json — the demo is
deterministic: parse → exactly these 4 flags → these exact dollar impacts.

Demo arithmetic encoded in app.fixtures.DEMO_LINE_ITEMS:
  duplicate     71046 billed twice @ $412 same date → impact = $412 (the 2nd line)
  upcode        99285 @ $2,340 with low-acuity dx J06.9; supported level 99283;
                counterfactual = 99283 mrf_negotiated_median $328.79 (real MGH)
                → 2340 − 328.79 = $2,011.21
  unbundle      14 CMP components totaling $690 instead of 80053 (bundled
                price $48, from ncci_pairs.json) → 690 − 48 = $642
  eob_mismatch  patient_balance $4,287 − EOB responsibility $3,875 = $412
                (same root cause as the duplicate)
  markup        does NOT fire: 85025 @ $24 ≤ band_high $27; 96374 @ $210 ≤
                band_high $261.75; flagged lines (71046/99285/components) are
                skipped; remaining lines have no benchmark row.
"""
import json

import pytest

from app.config import SEED_DIR, load_vertical
from app.engine.flags import detect_flags
from app.fixtures import demo_benchmarks

from fixtures import clean_job_spec, demo_job_spec


@pytest.fixture(scope="module")
def answer_key() -> dict:
    with open(SEED_DIR / "demo_answer_key.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def demo_flag_list():
    return detect_flags(demo_job_spec(), load_vertical(), demo_benchmarks())


def test_every_seeded_flag_fires_with_exact_impact(answer_key, demo_flag_list):
    computed = {(f.type, f.cpt): f.dollar_impact for f in demo_flag_list}
    for seeded in answer_key["seeded_flags"]:
        key = (seeded["type"], seeded.get("cpt"))
        assert key in computed, f"seeded flag did not fire: {seeded}"
        assert computed[key] == seeded["dollar_impact"], f"wrong impact for {key}"


def test_exactly_the_four_seeded_flags_and_no_more(answer_key, demo_flag_list):
    """PRD §10.3: 'parse → 4 flags'. In particular, no markup false positive."""
    assert len(demo_flag_list) == len(answer_key["seeded_flags"]) == 4
    assert [f.type for f in demo_flag_list] == ["duplicate", "upcode", "unbundle", "eob_mismatch"]


def test_flag_evidence_carries_the_seeded_facts(demo_flag_list):
    by_type = {f.type: f for f in demo_flag_list}
    assert by_type["duplicate"].evidence["dates"] == ["2026-06-02", "2026-06-02"]
    assert by_type["upcode"].evidence["supported"] == "99283"
    assert by_type["unbundle"].evidence["components_billed"] == 690.00
    assert by_type["unbundle"].evidence["bundled"] == 48.00
    assert by_type["eob_mismatch"].evidence == {"bill": 4287.00, "eob": 3875.00}


def test_demo_line_items_sum_to_statement_total():
    spec = demo_job_spec()
    assert round(sum(li.billed_amount for li in spec.bill.line_items), 2) == spec.bill.total_billed == 8432.00


def test_no_false_positives_on_clean_line_items():
    assert detect_flags(clean_job_spec(), load_vertical(), demo_benchmarks()) == []


def test_markup_fires_on_a_line_above_band():
    """Markup isn't seeded in the demo, but the detector must work:
    96374 @ $500 vs band_high $261.75 × 1.0 → impact $238.25."""
    spec = clean_job_spec()
    spec.bill.line_items[-1].billed_amount = 500.00  # the 96374 line
    flags = detect_flags(spec, load_vertical(), demo_benchmarks())
    assert [(f.type, f.cpt, f.dollar_impact) for f in flags] == [("markup", "96374", 238.25)]
