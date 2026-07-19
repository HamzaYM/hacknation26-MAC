"""New generalized-pipeline detectors in engine/flags.py (WS2).

Each detector: fire case + no-fire case + edges. Existing demo assertions live
in test_flags.py; this file covers phantom, NCCI PTP unbundle,
nsa_balance_billing, denial, units_error, absent_from_chargemaster, and the
line-level eob_mismatch upgrade. Fixture lookup + medical_bills.yaml only —
deterministic, no network.
"""
from app.config import load_vertical
from app.engine.flags import detect_flags
from app.engine.lookup import FIXTURE_HOSPITAL, FixtureLookup
from app.fixtures import demo_benchmarks
from app.models import JobSpec

CFG = load_vertical()
BM = demo_benchmarks()
D = "2026-06-02"


def _spec(bill_lines, eob_lines=None, *, hospital="Mercy General Hospital",
          patient_balance=None, patient_responsibility_total=None,
          denial_codes=None, insurance=None):
    return JobSpec.model_validate({
        "case_id": "c1", "patient": {},
        "insurance": insurance or {},
        "bill": {"facility_name": hospital, "account_number": "A1",
                 "total_billed": patient_balance, "patient_balance": patient_balance,
                 "line_items": bill_lines},
        "eob": {"line_items": eob_lines or [],
                "patient_responsibility_total": patient_responsibility_total,
                "denial_codes": denial_codes or []},
        "entities": [{"name": hospital, "kind": "facility"}],
    })


def _types(flags):
    return [f.type for f in flags]


# ── phantom ────────────────────────────────────────────────────────────────
def test_phantom_fires_for_bill_line_absent_from_a_covering_eob():
    bill = [
        {"cpt": "99283", "date_of_service": D, "billed_amount": 300.0},
        {"cpt": "71046", "date_of_service": D, "billed_amount": 200.0},  # never adjudicated
    ]
    eob = [{"cpt": "99283", "date_of_service": D, "billed_amount": 300.0, "allowed_amount": 245.0,
            "plan_paid": 245.0, "patient_responsibility": 0.0}]
    flags = detect_flags(_spec(bill, eob, patient_balance=200.0,
                               patient_responsibility_total=0.0), CFG, BM)
    ph = [f for f in flags if f.type == "phantom"]
    assert len(ph) == 1 and ph[0].cpt == "71046" and ph[0].dollar_impact == 200.0


def test_phantom_does_not_fire_without_eob_date_coverage():
    bill = [{"cpt": "71046", "date_of_service": "2026-07-09", "billed_amount": 200.0}]
    eob = [{"cpt": "99283", "date_of_service": D, "billed_amount": 300.0, "allowed_amount": 245.0,
            "plan_paid": 245.0, "patient_responsibility": 0.0}]  # different date
    flags = detect_flags(_spec(bill, eob, patient_responsibility_total=0.0), CFG, BM)
    assert "phantom" not in _types(flags)


def test_phantom_ignores_trivial_amounts_below_min():
    bill = [{"cpt": "99283", "date_of_service": D, "billed_amount": 300.0},
            {"cpt": "36415", "date_of_service": D, "billed_amount": 10.0}]  # < min_amount 25
    eob = [{"cpt": "99283", "date_of_service": D, "billed_amount": 300.0, "allowed_amount": 245.0,
            "plan_paid": 245.0, "patient_responsibility": 0.0}]
    flags = detect_flags(_spec(bill, eob, patient_responsibility_total=0.0), CFG, BM)
    assert "phantom" not in _types(flags)


# ── NCCI PTP unbundle ───────────────────────────────────────────────────────
def test_ptp_pair_fires_unbundle_on_column_2():
    # 71046 (col1) + 71045 (col2) same date → 71045 should be denied
    bill = [{"cpt": "71046", "date_of_service": D, "billed_amount": 412.0},
            {"cpt": "71045", "date_of_service": D, "billed_amount": 300.0}]
    flags = detect_flags(_spec(bill), CFG, BM)
    ub = [f for f in flags if f.type == "unbundle"]
    assert len(ub) == 1 and ub[0].cpt == "71045" and ub[0].dollar_impact == 300.0
    assert ub[0].evidence["ptp_pair"] == ["71046", "71045"]
    assert ub[0].evidence["severity"] == "medium"  # modifier_indicator 0


def test_ptp_pair_does_not_fire_when_only_one_code_present():
    bill = [{"cpt": "71046", "date_of_service": D, "billed_amount": 412.0}]
    assert "unbundle" not in _types(detect_flags(_spec(bill), CFG, BM))


# ── nsa_balance_billing ─────────────────────────────────────────────────────
def test_nsa_fires_for_in_network_balance_billing():
    bill = [{"cpt": "99283", "date_of_service": D, "billed_amount": 1000.0}]
    flags = detect_flags(_spec(bill, patient_balance=1000.0, patient_responsibility_total=400.0,
                               insurance={"network_status": "in_network"}), CFG, BM)
    nsa = [f for f in flags if f.type == "nsa_balance_billing"]
    assert len(nsa) == 1 and nsa[0].dollar_impact == 600.0
    assert nsa[0].evidence["do_not_negotiate"] is True


def test_nsa_fires_for_emergency_even_out_of_network():
    bill = [{"cpt": "99283", "date_of_service": D, "billed_amount": 1000.0}]
    flags = detect_flags(_spec(bill, patient_balance=1000.0, patient_responsibility_total=400.0,
                               insurance={"network_status": "out_of_network", "emergency_services": True}),
                         CFG, BM)
    assert "nsa_balance_billing" in _types(flags)


def test_nsa_no_fire_for_out_of_network_non_emergency():
    bill = [{"cpt": "99283", "date_of_service": D, "billed_amount": 1000.0}]
    flags = detect_flags(_spec(bill, patient_balance=1000.0, patient_responsibility_total=400.0,
                               insurance={"network_status": "out_of_network"}), CFG, BM)
    assert "nsa_balance_billing" not in _types(flags)


# ── denial ──────────────────────────────────────────────────────────────────
def test_denial_fires_on_zero_paid_line_with_denial_code():
    bill = [{"cpt": "97110", "date_of_service": D, "billed_amount": 500.0}]
    eob = [{"cpt": "97110", "date_of_service": D, "billed_amount": 500.0, "allowed_amount": 500.0,
            "plan_paid": 0.0, "patient_responsibility": 500.0}]
    flags = detect_flags(_spec(bill, eob, patient_balance=500.0, patient_responsibility_total=500.0,
                               denial_codes=["CO-197"]), CFG, BM)
    dn = [f for f in flags if f.type == "denial"]
    assert len(dn) == 1 and dn[0].dollar_impact == 500.0
    assert dn[0].evidence["denial_codes"] == ["CO-197"]  # reason passthrough


def test_denial_no_fire_when_plan_paid_nonzero():
    bill = [{"cpt": "97110", "date_of_service": D, "billed_amount": 500.0}]
    eob = [{"cpt": "97110", "date_of_service": D, "billed_amount": 500.0, "allowed_amount": 400.0,
            "plan_paid": 350.0, "patient_responsibility": 50.0}]
    flags = detect_flags(_spec(bill, eob, denial_codes=["CO-197"]), CFG, BM)
    assert "denial" not in _types(flags)


# ── units_error ─────────────────────────────────────────────────────────────
def test_units_error_fires_over_max_daily_units():
    # 96374 max_daily 1; 3 units billed 300 → per-unit 100, excess 2 → 200
    bill = [{"cpt": "96374", "date_of_service": D, "units": 3, "billed_amount": 300.0}]
    flags = detect_flags(_spec(bill), CFG, BM)
    ue = [f for f in flags if f.type == "units_error"]
    assert len(ue) == 1 and ue[0].dollar_impact == 200.0
    assert ue[0].evidence["excess_units"] == 2 and ue[0].evidence["basis"] == "max_daily_units"


def test_units_error_fires_when_bill_units_exceed_eob_units():
    bill = [{"cpt": "97110", "date_of_service": D, "units": 4, "billed_amount": 400.0}]
    eob = [{"cpt": "97110", "date_of_service": D, "units": 2, "billed_amount": 400.0,
            "allowed_amount": 200.0, "plan_paid": 200.0, "patient_responsibility": 0.0}]
    flags = detect_flags(_spec(bill, eob, patient_responsibility_total=0.0), CFG, BM)
    ue = [f for f in flags if f.type == "units_error"]
    assert len(ue) == 1 and ue[0].evidence["basis"] == "eob_allowed"
    assert ue[0].dollar_impact == 200.0  # per-unit 100 x excess 2


def test_units_error_no_fire_at_or_below_ceiling():
    bill = [{"cpt": "96374", "date_of_service": D, "units": 1, "billed_amount": 100.0}]
    assert "units_error" not in _types(detect_flags(_spec(bill), CFG, BM))


# ── absent_from_chargemaster (needs lookup) ─────────────────────────────────
def _mgh_spec(extra_line, entity="facility"):
    # >= mrf_completeness_min_rows (3) known MGH codes + one unknown facility code
    bill = [
        {"cpt": "71046", "date_of_service": D, "billed_amount": 100.0, "billing_entity": "facility"},
        {"cpt": "85025", "date_of_service": D, "billed_amount": 25.0, "billing_entity": "facility"},
        {"cpt": "96374", "date_of_service": D, "billed_amount": 200.0, "billing_entity": "facility"},
        extra_line,
    ]
    return _spec(bill, hospital=FIXTURE_HOSPITAL)


def test_absent_fires_for_facility_line_missing_from_complete_mrf():
    extra = {"cpt": "99999", "date_of_service": D, "billed_amount": 500.0, "billing_entity": "facility"}
    flags = detect_flags(_mgh_spec(extra), CFG, BM, lookup=FixtureLookup())
    af = [f for f in flags if f.type == "absent_from_chargemaster"]
    assert len(af) == 1 and af[0].cpt == "99999" and af[0].dollar_impact == 500.0
    assert af[0].evidence["severity"] == "low"


def test_absent_never_fires_for_professional_line():
    extra = {"cpt": "99999", "date_of_service": D, "billed_amount": 500.0, "billing_entity": "professional"}
    flags = detect_flags(_mgh_spec(extra), CFG, BM, lookup=FixtureLookup())
    assert "absent_from_chargemaster" not in _types(flags)


def test_absent_no_fire_when_mrf_incomplete():
    # only one known MGH code present → completeness < 3 → suppress (don't blame the charge)
    bill = [{"cpt": "71046", "date_of_service": D, "billed_amount": 100.0, "billing_entity": "facility"},
            {"cpt": "99999", "date_of_service": D, "billed_amount": 500.0, "billing_entity": "facility"}]
    flags = detect_flags(_spec(bill, hospital=FIXTURE_HOSPITAL), CFG, BM, lookup=FixtureLookup())
    assert "absent_from_chargemaster" not in _types(flags)


def test_absent_dormant_without_lookup():
    extra = {"cpt": "99999", "date_of_service": D, "billed_amount": 500.0, "billing_entity": "facility"}
    flags = detect_flags(_mgh_spec(extra), CFG, BM)  # no lookup
    assert "absent_from_chargemaster" not in _types(flags)


# ── line-level eob_mismatch upgrade ─────────────────────────────────────────
def test_eob_mismatch_adds_line_level_detail_when_available():
    bill = [{"cpt": "99283", "date_of_service": D, "billed_amount": 2000.0}]
    eob = [{"cpt": "99283", "date_of_service": D, "billed_amount": 2000.0, "allowed_amount": 245.0,
            "plan_paid": 200.0, "patient_responsibility": 45.0}]
    flags = detect_flags(_spec(bill, eob, patient_balance=2000.0,
                               patient_responsibility_total=45.0), CFG, BM)
    em = next(f for f in flags if f.type == "eob_mismatch")
    assert em.dollar_impact == 1955.0                     # aggregate preserved
    assert em.evidence["line_mismatches"][0]["code"] == "99283"
    assert em.evidence["line_mismatches"][0]["billed_vs_allowed"] == 1755.0
