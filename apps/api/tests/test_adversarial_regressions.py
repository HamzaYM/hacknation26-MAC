"""Permanent regressions for the adversarially-verified engine defects.

Each test pins the corrected behavior of one defect (or defect cluster) found in
the adversarial triage, rewritten in the suite's idioms (assert, not sys.exit).
Grouped by severity: H1-H5, then the M-clusters, then L1-L3.

  H1  (cpt,date)-keyed dedup — an unrelated same-code line on another date, and
      an independent PTP/duplicate on the same date, stay detectable.
  H2  totals.excess_above_band = sum of per-line excess (no un-benchmarked
      line's full billed amount smuggled in).
  H3  each unbundle lever's citation speaks its OWN flag's CPT/dollars.
  H4  units ceilings are keyed per (code, date_of_service).
  H5  upcode never fires a $0-impact "finding" when the counterfactual is absent.
  M1  the generalized (WS2) NSA path uses its own $1 tolerance, not the $100
      marker gate.
  M2  no NSA false-positive from a boilerplate OON marker + a reconciled ancillary.
  M3  NSA evidence['emergency'] is derived, never a hardcoded constant.
  M4/M5 denial only fires for a positive-responsibility line actually on the bill.
  M6  facility/professional split billing on one CPT/date is not a duplicate.
  M7  a UB-04 revenue code is not accused of being absent from the chargemaster.
  M8  billing_entity 'Facility' (any casing) is treated as a facility line.
  M9  a whitespace-padded low-acuity dx still triggers upcode.
  M10 'non-participating provider' phrasing is recognized as an OON marker.
  L1  totals.medicare == the sum of the per-line Medicare anchor dollars.
  L2  a resolved $0.00 Medicare rate still yields a fair band / excess signal.
  L3  a trailing-space facility_name still resolves the chargemaster lookup.
"""
from __future__ import annotations

from app.config import load_vertical
from app.engine.anchors import build_benchmark_report
from app.engine.dossier import build_dossier
from app.engine.flags import detect_flags
from app.engine.lookup import FIXTURE_HOSPITAL, FixtureLookup, MedicareRate
from app.fixtures import demo_benchmarks
from app.models import JobSpec

CFG = load_vertical()
BM = demo_benchmarks()
D1 = "2026-06-02"
D2 = "2026-06-05"


def _spec(bill_lines, eob_lines=None, *, hospital="Mercy General Hospital",
          patient_balance=None, patient_responsibility_total=None,
          denial_codes=None, insurance=None, entities=None):
    return JobSpec.model_validate({
        "case_id": "adv", "patient": {},
        "insurance": insurance or {},
        "bill": {"facility_name": hospital, "account_number": "A1",
                 "total_billed": patient_balance, "patient_balance": patient_balance,
                 "line_items": bill_lines},
        "eob": {"line_items": eob_lines or [],
                "patient_responsibility_total": patient_responsibility_total,
                "denial_codes": denial_codes or []},
        "entities": entities or [{"name": hospital, "kind": "facility"}],
    })


def _by_type(flags):
    out: dict = {}
    for f in flags:
        out.setdefault(f.type, []).append(f)
    return out


# ── H1: (cpt, date)-keyed implication ──────────────────────────────────────
def test_h1_duplicate_does_not_suppress_markup_on_another_date():
    bill = [
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 412.0},
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 412.0},  # same-day dup
        {"cpt": "71046", "date_of_service": D2, "billed_amount": 5000.0},  # unrelated overcharge
    ]
    bt = _by_type(detect_flags(_spec(bill), CFG, BM))
    assert len(bt["duplicate"]) == 1 and bt["duplicate"][0].dollar_impact == 412.0
    markups = bt.get("markup", [])
    expected = round(5000.0 - BM["71046"]["band_high"], 2)
    assert len(markups) == 1 and markups[0].dollar_impact == expected


def test_h1_ptp_fires_independently_on_each_date():
    bill = [
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 412.0},
        {"cpt": "71045", "date_of_service": D1, "billed_amount": 300.0},
        {"cpt": "71046", "date_of_service": D2, "billed_amount": 420.0},
        {"cpt": "71045", "date_of_service": D2, "billed_amount": 310.0},
    ]
    ub = [f for f in detect_flags(_spec(bill), CFG, BM) if f.type == "unbundle"]
    assert sorted(f.evidence.get("date") for f in ub) == [D1, D2]
    assert round(sum(f.dollar_impact for f in ub), 2) == 610.0


def test_h1_duplicate_of_c1_does_not_swallow_independent_ptp():
    bill = [
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 412.0},
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 412.0},  # duplicate of col-1
        {"cpt": "71045", "date_of_service": D1, "billed_amount": 300.0},  # PTP col-2 still fires
    ]
    got = {(f.type, f.cpt, f.dollar_impact) for f in detect_flags(_spec(bill), CFG, BM)}
    assert ("duplicate", "71046", 412.0) in got
    assert ("unbundle", "71045", 300.0) in got


# ── H2: totals excess = sum of per-line excess ─────────────────────────────
def test_h2_excess_total_excludes_unbenchmarked_line_billed_amount():
    lines = [
        {"cpt": "71046", "description": "CXR", "date_of_service": D1, "units": 1,
         "billed_amount": 100.0, "billing_entity": "facility"},
        {"cpt": "76499", "description": "Unlisted", "date_of_service": D1, "units": 1,
         "billed_amount": 5000.0, "billing_entity": "facility"},  # no Medicare/CM row
    ]
    rep = build_benchmark_report(_spec(lines, hospital=FIXTURE_HOSPITAL), FixtureLookup(), CFG)
    l0, l1 = rep["lines"]
    assert l1["fair_band"] is None and l1["excess_above_band"] == 0.0
    per_line = round(l0["excess_above_band"] + l1["excess_above_band"], 2)
    assert rep["totals"]["excess_above_band"] == per_line


# ── H3: per-flag unbundle citation provenance ──────────────────────────────
def test_h3_each_unbundle_lever_cites_its_own_flag():
    cmp_components = [
        {"cpt": c, "date_of_service": D1, "billed_amount": 50.0}
        for c in ("84295", "84132", "82374", "82435", "82947", "82565", "84520",
                  "82310", "84075", "84155", "84450", "84460", "82040", "82247")
    ]
    ptp_lines = [
        {"cpt": "71046", "date_of_service": D2, "billed_amount": 412.0},
        {"cpt": "71045", "date_of_service": D2, "billed_amount": 300.0},
    ]
    bill = cmp_components + ptp_lines
    spec = _spec(bill, patient_balance=sum(l["billed_amount"] for l in bill))
    flags = detect_flags(spec, CFG, BM)
    ub = {f.cpt: f for f in flags if f.type == "unbundle"}
    assert {"80053", "71045"} <= set(ub)
    dossier = build_dossier(spec, flags, BM, CFG, entity=spec.entities[0])
    lever = next(lv for lv in dossier.levers if lv.id == "error_unbundle_80053")
    cite = lever.citation or ""
    assert "80053" in cite and "71045" not in cite
    assert f"${ub['80053'].dollar_impact:,.2f}" in cite  # its own dollar figure
    assert "$300.00" not in cite


# ── H4: units ceilings per (code, date) ────────────────────────────────────
def test_h4_units_ceiling_is_per_date():
    bill = [
        {"cpt": "97110", "date_of_service": D1, "units": 2, "billed_amount": 200.0},  # compliant
        {"cpt": "97110", "date_of_service": D2, "units": 5, "billed_amount": 300.0},  # overbilled
    ]
    eob = [
        {"cpt": "97110", "date_of_service": D1, "units": 2, "billed_amount": 200.0,
         "allowed_amount": 200.0, "plan_paid": 200.0, "patient_responsibility": 0.0},
        {"cpt": "97110", "date_of_service": D2, "units": 1, "billed_amount": 300.0,
         "allowed_amount": 60.0, "plan_paid": 60.0, "patient_responsibility": 0.0},
    ]
    ue = [f for f in detect_flags(_spec(bill, eob, patient_responsibility_total=0.0), CFG, BM)
          if f.type == "units_error"]
    assert len(ue) == 1
    assert ue[0].evidence["date"] == D2 and ue[0].evidence["excess_units"] == 4
    assert ue[0].dollar_impact == 240.0


# ── H5: no $0-impact upcode ─────────────────────────────────────────────────
def test_h5_upcode_does_not_fire_with_zero_impact_when_benchmark_absent():
    bill = [{"cpt": "99285", "date_of_service": D1, "billed_amount": 5000.0, "dx_codes": ["J06.9"]}]
    up = [f for f in detect_flags(_spec(bill), CFG, {}) if f.type == "upcode"]
    assert up == []


# ── M1: WS2 tolerance distinct from marker gate ────────────────────────────
def test_m1_generalized_nsa_uses_its_own_tolerance():
    bill = [{"cpt": "99284", "description": "ED visit", "date_of_service": D1, "billed_amount": 450.0}]
    eob = [{"cpt": "99284", "date_of_service": D1, "billed_amount": 450.0, "allowed_amount": 400.0,
            "plan_paid": 350.0, "patient_responsibility": 400.0}]
    flags = detect_flags(_spec(bill, eob, patient_balance=450.0, patient_responsibility_total=400.0,
                               insurance={"network_status": "in_network"}), CFG, BM)
    nsa = [f for f in flags if f.type == "nsa"]
    assert len(nsa) == 1 and nsa[0].dollar_impact == 50.0  # 50 > $1 tolerance, < $100 marker gate


# ── M2: no NSA false positive from unrelated marker + reconciled ancillary ──
def test_m2_no_nsa_for_boilerplate_marker_and_reconciled_ancillary():
    bill = [
        {"cpt": "71046", "description": "CXR. Notice: this facility contracts with some "
         "out-of-network specialists.", "date_of_service": D1, "billed_amount": 1300.0},
        {"cpt": "00840", "description": "Anesthesia (in-network)", "date_of_service": D1,
         "billed_amount": 150.0},
    ]
    eob = [
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 1300.0, "allowed_amount": 1000.0,
         "plan_paid": 1000.0, "patient_responsibility": 1000.0},
        {"cpt": "00840", "date_of_service": D1, "billed_amount": 150.0, "allowed_amount": 150.0,
         "plan_paid": 0.0, "patient_responsibility": 150.0},
    ]
    entities = [
        {"name": "Mercy General Hospital", "kind": "facility", "balance": 1300.0},
        {"name": "Anesthesia Assoc", "kind": "anesthesia", "balance": 150.0},  # reconciled
    ]
    flags = detect_flags(_spec(bill, eob, patient_balance=1450.0,
                               patient_responsibility_total=1150.0,
                               insurance={"network_status": "in_network"}, entities=entities), CFG, BM)
    assert "nsa" not in [f.type for f in flags]


# ── M3: NSA evidence emergency is derived, not hardcoded ────────────────────
def test_m3_nsa_evidence_emergency_not_hardcoded_true():
    bill = [{"cpt": "70551", "description": "MRI brain read by an out-of-network radiologist",
             "date_of_service": D1, "billed_amount": 900.0}]
    eob = [{"cpt": "70551", "date_of_service": D1, "billed_amount": 900.0, "allowed_amount": 400.0,
            "plan_paid": 250.0, "patient_responsibility": 400.0}]
    entities = [{"name": "Suburban Radiology", "kind": "radiology", "balance": 900.0}]
    flags = detect_flags(_spec(bill, eob, patient_balance=900.0, patient_responsibility_total=400.0,
                               insurance={"network_status": "in_network", "emergency_services": False},
                               entities=entities), CFG, BM)
    nsa = [f for f in flags if f.type == "nsa"]
    # if it fires (marker path), it must not contradict the explicit emergency=False
    for f in nsa:
        assert f.evidence.get("emergency") is not True


# ── M4/M5: denial only on positive-responsibility bill lines ───────────────
def test_m4_denial_skips_bundled_zero_liability_line():
    bill = [
        {"cpt": "36415", "date_of_service": D1, "billed_amount": 15.0},   # bundled, $0 liability
        {"cpt": "97110", "date_of_service": D1, "billed_amount": 500.0},  # genuinely denied
    ]
    eob = [
        {"cpt": "36415", "date_of_service": D1, "billed_amount": 15.0, "allowed_amount": 0.0,
         "plan_paid": 0.0},  # patient_responsibility absent
        {"cpt": "97110", "date_of_service": D1, "billed_amount": 500.0, "allowed_amount": 500.0,
         "plan_paid": 0.0, "patient_responsibility": 500.0},
    ]
    dn = [f for f in detect_flags(_spec(bill, eob, patient_balance=500.0,
                                        patient_responsibility_total=500.0,
                                        denial_codes=["CO-197"]), CFG, BM) if f.type == "denial"]
    assert [(f.cpt, f.dollar_impact) for f in dn] == [("97110", 500.0)]


def test_m5_denial_does_not_fire_for_eob_only_line():
    bill = [{"cpt": "99213", "date_of_service": D1, "billed_amount": 150.0}]
    eob = [
        {"cpt": "99213", "date_of_service": D1, "billed_amount": 150.0, "allowed_amount": 120.0,
         "plan_paid": 120.0, "patient_responsibility": 0.0},
        {"cpt": "87491", "date_of_service": D1, "billed_amount": 300.0, "allowed_amount": 0.0,
         "plan_paid": 0.0},  # eob-only, never billed to patient
    ]
    dn = [f for f in detect_flags(_spec(bill, eob, patient_balance=0.0,
                                        patient_responsibility_total=0.0,
                                        denial_codes=["CO-50"]), CFG, BM) if f.type == "denial"]
    assert dn == []


# ── M6: split billing entities are not a duplicate ──────────────────────────
def test_m6_technical_professional_split_is_not_a_duplicate():
    bill = [
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 100.0, "billing_entity": "facility",
         "description": "CXR technical"},
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 50.0, "billing_entity": "professional",
         "description": "CXR professional read"},
    ]
    assert "duplicate" not in [f.type for f in detect_flags(_spec(bill), CFG, BM)]


# ── M7: revenue code not accused of chargemaster absence ────────────────────
def test_m7_revenue_code_not_flagged_absent():
    bill = [
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 100.0, "billing_entity": "facility"},
        {"cpt": "85025", "date_of_service": D1, "billed_amount": 25.0, "billing_entity": "facility"},
        {"cpt": "96374", "date_of_service": D1, "billed_amount": 200.0, "billing_entity": "facility"},
        {"cpt": "450", "description": "EMERGENCY ROOM", "date_of_service": D1,
         "billed_amount": 850.0, "billing_entity": "facility"},  # UB-04 revenue code
    ]
    flags = detect_flags(_spec(bill, hospital=FIXTURE_HOSPITAL), CFG, BM, lookup=FixtureLookup())
    assert not any(f.type == "absent_from_chargemaster" and f.cpt == "450" for f in flags)


# ── M8: case-insensitive facility gate ──────────────────────────────────────
def test_m8_facility_gate_is_case_insensitive():
    bill = [
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 100.0, "billing_entity": "facility"},
        {"cpt": "85025", "date_of_service": D1, "billed_amount": 25.0, "billing_entity": "facility"},
        {"cpt": "96374", "date_of_service": D1, "billed_amount": 200.0, "billing_entity": "facility"},
        {"cpt": "99999", "date_of_service": D1, "billed_amount": 500.0, "billing_entity": "Facility"},
    ]
    flags = detect_flags(_spec(bill, hospital=FIXTURE_HOSPITAL), CFG, BM, lookup=FixtureLookup())
    assert any(f.type == "absent_from_chargemaster" and f.cpt == "99999" for f in flags)


# ── M9: dx whitespace tolerance ─────────────────────────────────────────────
def test_m9_upcode_tolerates_padded_dx_code():
    clean = detect_flags(_spec([{"cpt": "99285", "date_of_service": D1, "billed_amount": 5000.0,
                                 "dx_codes": ["J06.9"]}]), CFG, BM)
    dirty = detect_flags(_spec([{"cpt": "99285", "date_of_service": D1, "billed_amount": 5000.0,
                                 "dx_codes": ["J06.9 "]}]), CFG, BM)
    clean_up = [f for f in clean if f.type == "upcode"]
    dirty_up = [f for f in dirty if f.type == "upcode"]
    assert len(clean_up) == 1 and len(dirty_up) == 1
    assert clean_up[0].dollar_impact == dirty_up[0].dollar_impact


# ── M10: non-participating provider phrasing recognized ─────────────────────
def test_m10_non_participating_marker_fires_nsa():
    bill = [{"cpt": "00840", "description": "Anesthesia, emergency abdominal surgery -- rendered by a "
             "non-participating provider", "date_of_service": D1, "billed_amount": 3120.0}]
    eob = [{"cpt": "00840", "date_of_service": D1, "billed_amount": 3120.0, "allowed_amount": 850.0,
            "plan_paid": 0.0, "patient_responsibility": 850.0}]
    entities = [{"name": "Anesthesia Assoc", "kind": "anesthesia", "balance": 3120.0}]
    flags = detect_flags(_spec(bill, eob, patient_balance=3120.0, patient_responsibility_total=850.0,
                               insurance={"payer_name": "BCBS"}, entities=entities), CFG, BM)
    nsa = [f for f in flags if f.type == "nsa"]
    assert len(nsa) == 1 and nsa[0].dollar_impact == 2270.0


# ── L1: medicare total == sum of per-line Medicare anchors ──────────────────
def test_l1_medicare_total_equals_sum_of_per_line_medicare():
    lines = [
        {"cpt": "71046", "date_of_service": D1, "units": 1, "billed_amount": 500.0,
         "billing_entity": "facility"},
        {"cpt": "96374", "date_of_service": D1, "units": 1, "billed_amount": 300.0,
         "billing_entity": "facility"},
        {"cpt": "85025", "date_of_service": D1, "units": 1, "billed_amount": 90.0,
         "billing_entity": "facility"},
    ]
    rep = build_benchmark_report(_spec(lines, hospital=FIXTURE_HOSPITAL), FixtureLookup(), CFG)
    per_line = []
    for ln in rep["lines"]:
        med = next((a for a in ln["anchors"] if a["method"] == "medicare"), None)
        if med is not None:
            per_line.append(med["value"] * ln["units"])
    assert rep["totals"]["medicare"] == round(sum(per_line), 2)


# ── L2: $0 Medicare rate still yields a fair band / excess ──────────────────
class _ZeroMedicareLookup(FixtureLookup):
    ZERO_CODE = "A4649"

    def medicare_rate(self, code, component="global"):
        if code == self.ZERO_CODE:
            return MedicareRate(code=code, component="facility", value=0.0,
                                formula="OPPS packaged (SI=N)", source_url=None,
                                version="cms-opps (packaged $0)")
        return super().medicare_rate(code, component)

    def code_in_chargemaster(self, hospital, code):
        if code == self.ZERO_CODE:
            return False
        return super().code_in_chargemaster(hospital, code)


def test_l2_zero_medicare_rate_is_not_treated_as_missing():
    lines = [{"cpt": "A4649", "description": "Surgical tray", "date_of_service": D1, "units": 1,
              "billed_amount": 600.0, "billing_entity": "facility"}]
    rep = build_benchmark_report(_spec(lines, hospital=FIXTURE_HOSPITAL), _ZeroMedicareLookup(), CFG)
    ln = rep["lines"][0]
    med = next((a for a in ln["anchors"] if a["method"] == "medicare"), None)
    assert med is not None and med["value"] == 0.0
    assert ln["fair_band"] is not None            # a real $0 rate resolved a band
    assert ln["rand_flag"] is True                # $600 above a $0 ceiling
    assert ln["excess_above_band"] == 600.0


# ── L3: trailing-space facility_name still resolves the lookup ──────────────
def test_l3_hospital_name_whitespace_still_resolves():
    bill = [
        {"cpt": "71046", "date_of_service": D1, "billed_amount": 100.0, "billing_entity": "facility"},
        {"cpt": "85025", "date_of_service": D1, "billed_amount": 25.0, "billing_entity": "facility"},
        {"cpt": "96374", "date_of_service": D1, "billed_amount": 200.0, "billing_entity": "facility"},
        {"cpt": "99999", "date_of_service": D1, "billed_amount": 500.0, "billing_entity": "facility"},
    ]
    flags = detect_flags(_spec(bill, hospital=FIXTURE_HOSPITAL + " "), CFG, BM, lookup=FixtureLookup())
    assert any(f.type == "absent_from_chargemaster" and f.cpt == "99999" for f in flags)
