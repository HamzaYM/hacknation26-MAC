"""Report builder — ranking, per-CPT lines, and the data-built recommendation."""
from app.engine.report import build_lines, build_recommendation, fair_total, rank_outcomes
from app.fixtures import DEMO_JOB_SPEC, demo_benchmarks, demo_flags
from app.models import JobSpec

SPEC = JobSpec.model_validate(DEMO_JOB_SPEC)
FAIR = 1095.0  # band_high sum over corrected set {99283,71046,80053,85025,96374}


def test_fair_total_is_band_high_over_corrected_set():
    assert fair_total(SPEC, demo_flags(), demo_benchmarks()) == FAIR


def test_rank_outcomes_orders_monetary_then_states():
    outcomes = [
        {"outcome_type": "documented_decline", "final_amount": None},
        {"outcome_type": "reduction", "final_amount": 1650.0},
        {"outcome_type": "charity_app_initiated", "final_amount": None},
        {"outcome_type": "reduction", "final_amount": 392.0},
        {"outcome_type": "callback", "final_amount": None},
    ]
    ranked = rank_outcomes(outcomes, FAIR)
    # monetary first, best (lowest % of fair band) on top
    assert [o.get("final_amount") for o in ranked[:2]] == [392.0, 1650.0]
    assert ranked[0]["achieved_pct_of_fair"] == 35.8
    assert ranked[1]["achieved_pct_of_fair"] == 150.7
    # then the frozen non-monetary order
    assert [o["outcome_type"] for o in ranked[2:]] == [
        "charity_app_initiated", "callback", "documented_decline"]


def test_lines_map_corrected_codes_and_allocate_settlement():
    lines = build_lines(SPEC, demo_flags(), demo_benchmarks(), settlement=1650.0)
    by_cpt = {l["cpt"]: l for l in lines}
    assert set(by_cpt) == {"99283", "71046", "80053", "85025", "96374"}
    assert by_cpt["99283"]["billed"] == 2340.0  # upcoded 99285 mapped to supported level
    assert by_cpt["71046"]["billed"] == 824.0   # both duplicate charges shown as billed
    assert by_cpt["80053"]["billed"] == 690.0   # unbundled components total
    assert by_cpt["71046"]["fair"] == 157.5     # band_high
    # settlement allocated proportionally across the shown lines
    assert abs(sum(l["achieved"] for l in lines) - 1650.0) < 0.05


def test_lines_without_settlement_have_no_achieved():
    lines = build_lines(SPEC, demo_flags(), demo_benchmarks(), settlement=None)
    assert lines and all(l["achieved"] is None for l in lines)


def test_recommendation_built_from_data():
    ranked = rank_outcomes([
        {"outcome_type": "reduction", "original_amount": 4287.0, "final_amount": 1650.0,
         "reduction_pct": 61.5, "reference_number": "MG-ADJ-2247",
         "target_entity": "Mercy General Hospital"},
        {"outcome_type": "charity_app_initiated", "final_amount": None,
         "reference_number": "BSEP-FA-1102", "target_entity": "Bay State Emergency Physicians"},
    ], FAIR)
    rec = build_recommendation(ranked)
    assert "$1,650" in rec and "MG-ADJ-2247" in rec
    assert "financial-assistance" in rec
    assert build_recommendation([]).startswith("No completed calls")
