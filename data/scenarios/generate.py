"""Deterministic scenario-suite generator (generalized-pipeline WS4).

Seeds 9 scenarios (Maya #1 + 8 archetypes) ENTIRELY from real chargemaster rows
via the lookup layer + real CMS Medicare rates, then runs the REAL engine
pipeline (reconcile -> detect_flags -> build_benchmark_report) to compute each
answer key. The LLM is the mouth, not the brain: no number here is authored by
hand — every billed amount is a real gross_charge/negotiated_dollar/cross-payer
median from the DB, every flag dollar-impact is the engine's own arithmetic, and
every benchmark anchor carries the lookup provenance the engine attached.

Data source (decision #7, hermetic): the lookup is a SqliteLookup over a mini
chargemaster DB built from the COMMITTED real-data extract
`data/seed/chargemaster_test_extract.json` (217 rows sampled once from
`chargemasters_demo.db` by scripts/build_chargemaster_fixture.py) plus
`data/seed/medicare_rates.json` (real CMS PFS/OPPS/CLFS 2026, Boston MA-01).
Using the committed extract — the SAME rows apps/api/tests use — is what makes
`generate.py --check` byte-stable and lets test_scenario_suite.py reproduce every
answer key without the multi-hundred-thousand-row source DB present. The rows are
real (provenance stamped in the extract); pointing at the full DB is unnecessary
and would break determinism because the extract is a fixed sample.

Determinism knobs: fixed service dates + patient personas (fictional people),
fixed case_ids (= scenario_id), payers taken verbatim from real payer_name
strings present in the DB for that hospital+code (decision #8), JSON emitted
sort_keys + indent=2, and PDFs rendered with a FIXED creation date
(data/demo_docs/generate_demo_pdfs.py FIXED_PDF_DATE).

Usage:
    python data/scenarios/generate.py            # (re)write all artifacts
    python data/scenarios/generate.py --check    # verify byte-identical, exit 1 on drift
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "tests" / "fixtures"))

from app.config import load_vertical  # noqa: E402
from app.engine.anchors import build_benchmark_report  # noqa: E402
from app.engine.flags import detect_flags, load_ncci_table  # noqa: E402
from app.fixtures import DEMO_JOB_SPEC, demo_benchmarks  # noqa: E402
from app.models import JobSpec  # noqa: E402
from mini_chargemaster import build_mini_chargemaster_db  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "data" / "demo_docs"))
from generate_demo_pdfs import render_scenario_bill_pdf, render_scenario_eob_pdf  # noqa: E402

SCENARIOS_DIR = REPO_ROOT / "data" / "scenarios"

# Engine emits DerivedFlag.type "nsa"; contracts/scenario.schema.json's
# expected_flags enum names the same detector "nsa_balance_billing" (and the
# scenarios router maps it back). Serialize the contract name in answer keys.
_FLAG_TYPE_TO_CONTRACT = {"nsa": "nsa_balance_billing"}

# Real public hospital identifiers (name MUST match the chargemaster extract
# exactly so the lookup resolves rows). EIN/CCN are the real values carried in
# data/seed/chargemaster_test_extract.json.
HOSPITALS = {
    "MGH": {"name": "Massachusetts General Hospital", "ein": "04-2697983",
            "ccn": "220071", "city": "Boston", "state": "MA",
            "address": "55 Fruit Street, Boston, MA 02114"},
    "BWH": {"name": "Brigham and Women's Hospital", "ein": "04-2312909",
            "ccn": "220110", "city": "Boston", "state": "MA",
            "address": "75 Francis Street, Boston, MA 02115"},
    "NWH": {"name": "Newton-Wellesley Hospital", "ein": "04-2103611",
            "ccn": "220087", "city": "Newton", "state": "MA",
            "address": "2014 Washington Street, Newton, MA 02462"},
}

PROVENANCE_STATIC = {
    "generator": "data/scenarios/generate.py",
    "chargemaster_version": "chargemaster_test_extract.json (real MGB MRF v3.0.0 extract of chargemasters_demo.db)",
    "medicare_version": "medicare_rates.json (CMS PFS/OPPS/CLFS 2026, Boston MA-01)",
    "config_version": "medical_bills",
    "lookup_backend": "sqlite",
}


# ── lookup construction (shared with the test suite) ──────────────────────
def build_scenario_lookup(db_path: Path | None = None):
    """SqliteLookup over the committed real-data extract + Medicare seed.

    A fixed DB basename keeps lookup.version() == "sqlite:scenario_chargemaster.db"
    stable regardless of the temp directory, so answer-key provenance is
    byte-reproducible. test_scenario_suite.py builds an identical lookup.
    """
    from app.engine.lookup_sqlite import SqliteLookup
    if db_path is None:
        db_path = Path(tempfile.mkdtemp()) / "scenario_chargemaster.db"
    build_mini_chargemaster_db(db_path)
    return SqliteLookup(str(db_path))


# ── scenario definitions (every billed amount pulled from the lookup) ──────
def _line(cpt, desc, dos, billed, *, units=1, entity="facility", dx=None):
    li = {"cpt": cpt, "description": desc, "date_of_service": dos,
          "units": units, "billed_amount": round(float(billed), 2),
          "billing_entity": entity}
    if dx:
        li["dx_codes"] = list(dx)
    return li


def _spec(scenario_id, patient, insurance, bill, eob, entities):
    return {
        "case_id": scenario_id,
        "patient": patient,
        "insurance": insurance,
        "financial_profile": {},
        "authorizations": {},
        "bill": bill,
        "eob": eob,
        "derived_flags": [],
        "entities": entities,
    }


def scenario_definitions(lk) -> list[dict]:
    """Each entry: {id, archetype, title, narrative, hospital_key, coverage,
    patient, provider_entities, service_date, diagnosis, spec}. Billed amounts,
    EOB allowed amounts, and thresholds are all read from the lookup `lk` so
    the suite is seeded from real rows, never hand-authored."""
    g = lk.gross_charge
    xmed = lambda h, c: (lk.cross_payer_stats(h, c) or {}).get("median")  # noqa: E731
    out: list[dict] = []

    # ── sc01 — Maya's flagship case, reproduced through the generalized flow ─
    # The one scenario NOT re-derived from the DB: it IS the locked fixture
    # (data/seed/demo_answer_key.json). The generator runs the real pipeline on
    # it and test_scenario_suite asserts the locked flags reproduce exactly.
    out.append({
        "id": "sc01_maya_baseline", "archetype": "maya_baseline",
        "hospital_key": None,
        "title": "Maya Chen — ER overbill (duplicate + upcode + unbundle + EOB mismatch)",
        "narrative": ("Maya's flagship ER statement: a $8,432 bill with a duplicated "
                      "chest X-ray, an upcoded level-5 visit, an unbundled metabolic "
                      "panel, and an EOB that only adjudicated one of the X-rays."),
        "coverage": {"status": "insured",
                     "payer_name": "Blue Cross Blue Shield of Massachusetts",
                     "plan_name": "PPO", "member_id": "XYZ123456",
                     "network_status": "in_network"},
        "patient": {"name": "Maya Chen", "dob": "1995-03-14", "account_number": "MG-4471983"},
        "provider_entities": [
            {"name": "Mercy General Hospital", "entity_type": "facility", "balance": 4287.00},
            {"name": "Bay State Emergency Physicians", "entity_type": "professional", "balance": 640.00},
        ],
        "service_date": "2026-06-02",
        "diagnosis": "J06.9 - Acute upper respiratory infection",
        "spec": _maya_spec(),
    })

    # ── sc02 — duplicate charge (Newton-Wellesley) ──────────────────────────
    H = HOSPITALS["NWH"]["name"]
    dos = "2026-03-11"
    cxr = g(H, "71046")          # real NWH gross for chest X-ray 2-view
    out.append({
        "id": "sc02_duplicate", "archetype": "duplicate_charge", "hospital_key": "NWH",
        "title": "Priya Nair — chest X-ray billed twice",
        "narrative": ("An ER chest X-ray (CPT 71046) appears twice on the same date on "
                      "Priya's Newton-Wellesley itemized bill — a classic duplicate line."),
        "coverage": {"status": "insured", "payer_name": "CIGNA [1006]",
                     "plan_name": "HB CH CIGNA HMO / PPO", "member_id": "CIG-2210",
                     "network_status": "in_network"},
        "patient": {"name": "Priya Nair", "dob": "1988-07-22", "account_number": "NWH-2026-0311"},
        "provider_entities": [{"name": H, "entity_type": "facility", "balance": None}],
        "service_date": dos,
        "diagnosis": "R05.9 - Cough",
        "spec": _spec(
            "sc02_duplicate",
            {"legal_name": "Priya Nair", "dob": "1988-07-22"},
            {"payer_name": "CIGNA [1006]", "plan_type": "HB CH CIGNA HMO / PPO",
             "member_id": "CIG-2210"},
            {"facility_name": H, "nonprofit_status": True, "statement_date": "2026-03-20",
             "due_date": "2026-04-19", "account_number": "NWH-2026-0311", "is_itemized": True,
             "patient_balance": round(cxr * 2 + g(H, "99285"), 2),
             "line_items": [
                 _line("99285", "Emergency department visit, high severity", dos, g(H, "99285")),
                 _line("71046", "Radiologic exam, chest, 2 views", dos, cxr),
                 _line("71046", "Radiologic exam, chest, 2 views", dos, cxr),
                 _line("96360", "IV hydration, initial hour", dos, g(H, "96360")),
             ]},
            {},  # insured but pre-EOB: no adjudication artifact
            [{"name": H, "kind": "facility", "balance": round(cxr * 2 + g(H, "99285"), 2)}],
        ),
    })

    # ── sc03 — upcoded ER (MGH): 99285 billed where records support 99283 ───
    H = HOSPITALS["MGH"]["name"]
    dos = "2026-04-05"
    out.append({
        "id": "sc03_upcoded_er", "archetype": "upcoded_er", "hospital_key": "MGH",
        "title": "Marcus Webb — level-5 ER visit on a low-acuity diagnosis",
        "narrative": ("Marcus was billed a level-5 emergency visit (CPT 99285) for an "
                      "acute upper-respiratory infection (J06.9). The records support a "
                      "level-3 visit (99283); the difference is an upcode."),
        "coverage": {"status": "insured", "payer_name": "AETNA [1001]",
                     "plan_name": "HB AMC AETNA HMO", "member_id": "AET-88102",
                     "network_status": "in_network"},
        "patient": {"name": "Marcus Webb", "dob": "1979-01-30", "account_number": "MGH-2026-0405"},
        "provider_entities": [{"name": H, "entity_type": "facility", "balance": None}],
        "service_date": dos,
        "diagnosis": "J06.9 - Acute upper respiratory infection",
        "spec": _spec(
            "sc03_upcoded_er",
            {"legal_name": "Marcus Webb", "dob": "1979-01-30"},
            {"payer_name": "AETNA [1001]", "plan_type": "HB AMC AETNA HMO", "member_id": "AET-88102"},
            {"facility_name": H, "nonprofit_status": True, "statement_date": "2026-04-14",
             "due_date": "2026-05-14", "account_number": "MGH-2026-0405", "is_itemized": True,
             "patient_balance": round(g(H, "99285") + g(H, "71045") + g(H, "96360"), 2),
             "line_items": [
                 _line("99285", "Emergency department visit, high severity (level 5)", dos,
                       g(H, "99285"), dx=["J06.9"]),
                 _line("71045", "Radiologic exam, chest, single view", dos, g(H, "71045")),
                 _line("96360", "IV hydration, initial hour", dos, g(H, "96360")),
             ]},
            {},
            [{"name": H, "kind": "facility",
              "balance": round(g(H, "99285") + g(H, "71045") + g(H, "96360"), 2)}],
        ),
    })

    # ── sc04 — unbundled panel (BWH): CMP (80053) billed with its BMP subset ─
    # NCCI PTP edit 80053/80048 — the comprehensive metabolic panel subsumes the
    # basic metabolic panel; billing both is unbundling. Impact = billed 80048.
    H = HOSPITALS["BWH"]["name"]
    dos = "2026-05-20"
    out.append({
        "id": "sc04_unbundled_panel", "archetype": "unbundled_panel", "hospital_key": "BWH",
        "title": "Elena Sorto — metabolic panel unbundled (80053 + 80048)",
        "narrative": ("Elena's Brigham lab bill lists both a comprehensive metabolic "
                      "panel (80053) and a basic metabolic panel (80048) on the same day. "
                      "The comprehensive panel already includes the basic — an NCCI "
                      "procedure-to-procedure unbundle."),
        "coverage": {"status": "insured", "payer_name": "BLUE CROSS BLUE SHIELD [110001]",
                     "plan_name": "HB AMC BLUE CROSS HMO", "member_id": "BCB-55031",
                     "network_status": "in_network"},
        "patient": {"name": "Elena Sorto", "dob": "1990-11-08", "account_number": "BWH-2026-0520"},
        "provider_entities": [{"name": H, "entity_type": "facility", "balance": None}],
        "service_date": dos,
        "diagnosis": "R53.83 - Fatigue",
        "spec": _spec(
            "sc04_unbundled_panel",
            {"legal_name": "Elena Sorto", "dob": "1990-11-08"},
            {"payer_name": "BLUE CROSS BLUE SHIELD [110001]", "plan_type": "HB AMC BLUE CROSS HMO",
             "member_id": "BCB-55031"},
            {"facility_name": H, "nonprofit_status": True, "statement_date": "2026-05-29",
             "due_date": "2026-06-28", "account_number": "BWH-2026-0520", "is_itemized": True,
             "patient_balance": round(g(H, "80053") + g(H, "80048") + g(H, "96360"), 2),
             "line_items": [
                 _line("80053", "Comprehensive metabolic panel", dos, g(H, "80053")),
                 _line("80048", "Basic metabolic panel", dos, g(H, "80048")),
                 _line("96360", "IV hydration, initial hour", dos, g(H, "96360")),
             ]},
            {},
            [{"name": H, "kind": "facility",
              "balance": round(g(H, "80053") + g(H, "80048") + g(H, "96360"), 2)}],
        ),
    })

    # ── sc05 — self-pay gross (MGH): full chargemaster list, no insurance ────
    H = HOSPITALS["MGH"]["name"]
    dos = "2026-02-14"
    sp_lines = [
        _line("70450", "CT head/brain without contrast", dos, g(H, "70450")),
        _line("72110", "X-ray, lumbar spine, 4+ views", dos, g(H, "72110")),
        _line("96360", "IV hydration, initial hour", dos, g(H, "96360")),
        _line("36415", "Routine venipuncture", dos, g(H, "36415")),
    ]
    sp_total = round(sum(li["billed_amount"] for li in sp_lines), 2)
    out.append({
        "id": "sc05_self_pay_gross", "archetype": "self_pay_gross", "hospital_key": "MGH",
        "title": "Darnell Price — uninsured, billed full chargemaster gross",
        "narrative": ("Darnell had no insurance and was charged Mass General's full "
                      "chargemaster list price for a CT and imaging visit — multiples of "
                      "both Medicare and the hospital's own posted cash price."),
        "coverage": {"status": "self_pay", "payer_name": None, "plan_name": None,
                     "member_id": None, "network_status": None},
        "patient": {"name": "Darnell Price", "dob": "1985-06-03", "account_number": "MGH-2026-0214"},
        "provider_entities": [{"name": H, "entity_type": "facility", "balance": sp_total}],
        "service_date": dos,
        "diagnosis": "S06.0X0A - Concussion without loss of consciousness",
        "spec": _spec(
            "sc05_self_pay_gross",
            {"legal_name": "Darnell Price", "dob": "1985-06-03"},
            {},  # self-pay
            {"facility_name": H, "nonprofit_status": True, "statement_date": "2026-02-23",
             "due_date": "2026-03-25", "account_number": "MGH-2026-0214", "is_itemized": True,
             "patient_balance": sp_total, "line_items": sp_lines},
            {},  # no EOB — self-pay
            [{"name": H, "kind": "facility", "balance": sp_total}],
        ),
    })

    # ── sc06 — EOB mismatch (NWH): provider bills gross the insurer wrote off ─
    H = HOSPITALS["NWH"]["name"]
    dos = "2026-05-02"
    m6 = {c: xmed(H, c) for c in ("70450", "72110", "96360")}
    bill6 = [
        _line("70450", "CT head/brain without contrast", dos, g(H, "70450")),
        _line("72110", "X-ray, lumbar spine, 4+ views", dos, g(H, "72110")),
        _line("96360", "IV hydration, initial hour", dos, g(H, "96360")),
    ]
    balance6 = round(sum(li["billed_amount"] for li in bill6), 2)
    eob6_lines = [
        {"cpt": c, "description": d, "date_of_service": dos, "units": 1,
         "billed_amount": g(H, c), "allowed_amount": round(m6[c], 2),
         "plan_paid": round(m6[c], 2), "patient_responsibility": 0.0}
        for c, d in (("70450", "CT head/brain without contrast"),
                     ("72110", "X-ray, lumbar spine, 4+ views"),
                     ("96360", "IV hydration, initial hour"))
    ]
    out.append({
        "id": "sc06_eob_mismatch", "archetype": "eob_mismatch", "hospital_key": "NWH",
        "title": "Grace Kimura — billed the gross charge her plan already adjusted",
        "narrative": ("Grace's EOB shows the plan allowed and paid the negotiated amount "
                      "with $0 left to her, but the hospital's statement bills her the full "
                      "gross charge — the contractual write-down was never applied."),
        "coverage": {"status": "insured", "payer_name": "TUFTS HEALTH PLAN [170001]",
                     "plan_name": "HB CH TUFTS", "member_id": "TUF-31007",
                     "network_status": "in_network"},
        "patient": {"name": "Grace Kimura", "dob": "1994-09-19", "account_number": "NWH-2026-0502"},
        "provider_entities": [{"name": H, "entity_type": "facility", "balance": balance6}],
        "service_date": dos,
        "diagnosis": "M54.5 - Low back pain",
        "spec": _spec(
            "sc06_eob_mismatch",
            {"legal_name": "Grace Kimura", "dob": "1994-09-19"},
            {"payer_name": "TUFTS HEALTH PLAN [170001]", "plan_type": "HB CH TUFTS",
             "member_id": "TUF-31007"},
            {"facility_name": H, "nonprofit_status": True, "statement_date": "2026-05-11",
             "due_date": "2026-06-10", "account_number": "NWH-2026-0502", "is_itemized": True,
             "patient_balance": balance6, "line_items": bill6},
            {"claim_number": "THP-2026-40771", "patient_responsibility_total": 0.0,
             "denial_codes": [], "line_items": eob6_lines},
            [{"name": H, "kind": "facility", "balance": balance6}],
        ),
    })

    # ── sc07 — OON balance bill / No Surprises Act (BWH) ─────────────────────
    # Emergency ER at an in-network Brigham; an out-of-network anesthesia group
    # balance-bills above the EOB in-network responsibility. Fires the unified
    # "nsa" flag (marker path: OON line marker + ancillary anesthesia entity)
    # AND supplies insurance.network_status/emergency for the generalized path.
    H = HOSPITALS["BWH"]["name"]
    dos = "2026-06-18"
    er_gross = g(H, "99285")
    anes_billed = 2800.00           # OON anesthesia surprise balance (protected input, cf. Nina)
    eob_resp7 = round(0.2 * xmed(H, "99285"), 2)   # in-network cost share on the ER portion
    balance7 = round(eob_resp7 + anes_billed, 2)
    out.append({
        "id": "sc07_oon_balance_bill", "archetype": "oon_balance_bill", "hospital_key": "BWH",
        "title": "Tomas Vega — surprise out-of-network anesthesia bill (No Surprises Act)",
        "narrative": ("Tomas went to an in-network Brigham ER, but the anesthesia group "
                      "was out-of-network and balance-billed him far above his in-network "
                      "responsibility — a No Surprises Act violation, cited not negotiated."),
        "coverage": {"status": "insured", "payer_name": "CIGNA ALTERNATE [1018]",
                     "plan_name": "HB AMC CIGNA NEW BUSINESS DISCOUNT", "member_id": "CIA-70045",
                     "network_status": "in_network", "emergency_services": True},
        "patient": {"name": "Tomas Vega", "dob": "1983-12-11", "account_number": "BWH-2026-0618"},
        "provider_entities": [
            {"name": H, "entity_type": "facility", "balance": eob_resp7},
            {"name": "Bay State Anesthesia Associates", "entity_type": "professional",
             "balance": anes_billed},
        ],
        "service_date": dos,
        "diagnosis": "S52.501A - Fracture of the radius",
        "spec": _spec(
            "sc07_oon_balance_bill",
            {"legal_name": "Tomas Vega", "dob": "1983-12-11"},
            {"payer_name": "CIGNA ALTERNATE [1018]", "plan_type": "HB AMC CIGNA NEW BUSINESS DISCOUNT",
             "member_id": "CIA-70045", "network_status": "in_network", "emergency_services": True},
            {"facility_name": H, "nonprofit_status": True, "statement_date": "2026-06-27",
             "due_date": "2026-07-27", "account_number": "BWH-2026-0618", "is_itemized": True,
             "patient_balance": balance7,
             "line_items": [
                 _line("99285", "Emergency department visit, high severity (level 5)", dos, er_gross),
                 _line("01922", "Anesthesia services (out-of-network provider)", dos, anes_billed,
                       entity="professional"),
             ]},
            {"claim_number": "CIG-2026-99120", "patient_responsibility_total": eob_resp7,
             "denial_codes": [], "line_items": []},
            [{"name": H, "kind": "facility", "balance": eob_resp7},
             {"name": "Bay State Anesthesia Associates", "kind": "anesthesia", "balance": anes_billed}],
        ),
    })

    # ── sc08 — clean but overpriced (BWH): zero error flags, pure benchmark ──
    H = HOSPITALS["BWH"]["name"]
    dos = "2026-04-22"
    clean_lines = [
        _line("70450", "CT head/brain without contrast", dos, g(H, "70450")),
        _line("72110", "X-ray, lumbar spine, 4+ views", dos, g(H, "72110")),
        _line("96360", "IV hydration, initial hour", dos, g(H, "96360")),
    ]
    clean_total = round(sum(li["billed_amount"] for li in clean_lines), 2)
    out.append({
        "id": "sc08_clean_overpriced", "archetype": "clean_overpriced", "hospital_key": "BWH",
        "title": "Aisha Bello — correctly coded, but billed far above the market",
        "narrative": ("Aisha's Brigham bill has no coding errors and no EOB mismatch — "
                      "every line is legitimate. But the charges sit far above what every "
                      "other payer negotiates for the same codes: a pure benchmarking case."),
        "coverage": {"status": "insured", "payer_name": "CENTERS OF EXCELLENCE [1026]",
                     "plan_name": "HB AMC MGBHP TRANSPLANT", "member_id": "COE-11228",
                     "network_status": "in_network"},
        "patient": {"name": "Aisha Bello", "dob": "1976-02-27", "account_number": "BWH-2026-0422"},
        "provider_entities": [{"name": H, "entity_type": "facility", "balance": clean_total}],
        "service_date": dos,
        "diagnosis": "R51.9 - Headache",
        "spec": _spec(
            "sc08_clean_overpriced",
            {"legal_name": "Aisha Bello", "dob": "1976-02-27"},
            {"payer_name": "CENTERS OF EXCELLENCE [1026]", "plan_type": "HB AMC MGBHP TRANSPLANT",
             "member_id": "COE-11228"},
            {"facility_name": H, "nonprofit_status": True, "statement_date": "2026-05-01",
             "due_date": "2026-05-31", "account_number": "BWH-2026-0422", "is_itemized": True,
             "patient_balance": clean_total, "line_items": clean_lines},
            {},  # insured, pre-EOB — nothing miscoded or misadjudicated
            [{"name": H, "kind": "facility", "balance": clean_total}],
        ),
    })

    # ── sc09 — denial-driven (MGH): $0-paid EOB line with a denial reason ────
    H = HOSPITALS["MGH"]["name"]
    dos = "2026-03-27"
    ct_gross = g(H, "70450")
    iv_gross = g(H, "96360")
    iv_med = round(xmed(H, "96360"), 2)
    bill9 = [
        _line("70450", "CT head/brain without contrast", dos, ct_gross),
        _line("96360", "IV hydration, initial hour", dos, iv_gross),
    ]
    eob9_lines = [
        {"cpt": "70450", "description": "CT head/brain without contrast", "date_of_service": dos,
         "units": 1, "billed_amount": ct_gross, "allowed_amount": ct_gross,
         "plan_paid": 0.0, "patient_responsibility": ct_gross},         # DENIED
        {"cpt": "96360", "description": "IV hydration, initial hour", "date_of_service": dos,
         "units": 1, "billed_amount": iv_gross, "allowed_amount": iv_med,
         "plan_paid": iv_med, "patient_responsibility": 0.0},           # paid
    ]
    out.append({
        "id": "sc09_denial_driven", "archetype": "denial_driven", "hospital_key": "MGH",
        "title": "Owen Fletcher — CT denied for missing prior authorization",
        "narrative": ("Owen's plan denied his CT scan (denial code 197, prior "
                      "authorization missing) and paid $0, leaving the full charge to him. "
                      "The denial is appealable — the provider never obtained the auth."),
        "coverage": {"status": "insured", "payer_name": "COMMONWEALTH CARE ALLIANCE [1007]",
                     "plan_name": "HB MGH COMMONWEALTH CARE ALLIANCE", "member_id": "CCA-90514",
                     "network_status": "in_network"},
        "patient": {"name": "Owen Fletcher", "dob": "1968-08-16", "account_number": "MGH-2026-0327"},
        "provider_entities": [{"name": H, "entity_type": "facility", "balance": ct_gross}],
        "service_date": dos,
        "diagnosis": "G43.909 - Migraine",
        "spec": _spec(
            "sc09_denial_driven",
            {"legal_name": "Owen Fletcher", "dob": "1968-08-16"},
            {"payer_name": "COMMONWEALTH CARE ALLIANCE [1007]",
             "plan_type": "HB MGH COMMONWEALTH CARE ALLIANCE", "member_id": "CCA-90514"},
            {"facility_name": H, "nonprofit_status": True, "statement_date": "2026-04-05",
             "due_date": "2026-05-05", "account_number": "MGH-2026-0327", "is_itemized": True,
             "patient_balance": ct_gross, "line_items": bill9},
            {"claim_number": "CCA-2026-33418", "patient_responsibility_total": ct_gross,
             "denial_codes": ["197"], "line_items": eob9_lines},
            [{"name": H, "kind": "facility", "balance": ct_gross}],
        ),
    })

    return out


def _maya_spec() -> dict:
    """Maya's exact fixture JobSpec, but re-homed onto the scenario case_id so
    build_benchmark_report stamps a stable case_id in sc01's answer key. The
    bill/eob/flags/entities are byte-identical to app.fixtures.DEMO_JOB_SPEC."""
    import copy
    spec = copy.deepcopy(DEMO_JOB_SPEC)
    spec["case_id"] = "sc01_maya_baseline"
    spec["derived_flags"] = []            # recomputed by the pipeline
    spec["financial_profile"] = {}        # keep answer-key generation config-free
    spec["authorizations"] = {}
    return spec


# ── pipeline + answer-key assembly ────────────────────────────────────────
def run_pipeline(spec_dict: dict, lookup, config: dict, ncci: dict):
    """The REAL engine pipeline for one scenario: (flags, benchmark_report)."""
    spec = JobSpec.model_validate(spec_dict)
    flags = detect_flags(spec, config, demo_benchmarks(), ncci, lookup=lookup)
    report = build_benchmark_report(spec, lookup, config)
    return flags, report


def serialize_flags(flags) -> list[dict]:
    """DerivedFlag list -> answer-key expected_flags (contract flag names)."""
    out = []
    for f in flags:
        ftype = _FLAG_TYPE_TO_CONTRACT.get(f.type, f.type)
        entry: dict = {"type": ftype, "code": f.cpt, "dollar_impact": round(f.dollar_impact, 2)}
        sev = (f.evidence or {}).get("severity")
        if sev:
            entry["severity"] = sev
        codes = (f.evidence or {}).get("ptp_pair")
        if codes:
            entry["codes"] = list(codes)
        detail = _flag_detail(f)
        if detail:
            entry["detail"] = detail
        out.append(entry)
    return out


def _flag_detail(f) -> str | None:
    ev = f.evidence or {}
    if f.type == "duplicate":
        return f"{f.cpt} billed {ev.get('count')}x on the same date"
    if f.type == "upcode":
        return f"{f.cpt} billed; records support {ev.get('supported')}"
    if f.type == "unbundle" and ev.get("ptp_pair"):
        return f"{ev['ptp_pair'][1]} bundled into {ev['ptp_pair'][0]} (NCCI PTP)"
    if f.type == "unbundle":
        return f"{ev.get('component_count')} components billed instead of {f.cpt}"
    if f.type == "nsa":
        return "protected out-of-network emergency/ancillary balance (No Surprises Act)"
    if f.type == "eob_mismatch":
        return "provider balance exceeds the EOB patient responsibility"
    if f.type == "denial":
        return f"plan paid $0 with denial code(s) {ev.get('denial_codes')}"
    return None


def build_ask(report: dict) -> dict:
    """Answer-key `ask`: headline anchor/target/floor band + Medicare multiples,
    all pulled straight from the BenchmarkReport totals/lines (no new numbers)."""
    t = report.get("totals", {})
    return {
        "anchor": t.get("ask_anchor"),
        "target": t.get("ask_target"),
        "floor": t.get("floor"),
        "total_medicare_multiple": t.get("medicare_multiple"),
        "excess_above_band": t.get("excess_above_band"),
        "per_line_multiples": [
            {"code": ln["code"], "medicare_multiple": ln["medicare_multiple"],
             "rand_flag": ln.get("rand_flag", False)}
            for ln in report.get("lines", []) if ln.get("medicare_multiple") is not None
        ],
    }


def build_talking_points(flags, report: dict) -> list[str]:
    """Citable claims for the voice agent — each references a flag or an anchor,
    no free-floating numbers (every figure below is in expected_flags/ask)."""
    points: list[str] = []
    for f in flags:
        ftype = _FLAG_TYPE_TO_CONTRACT.get(f.type, f.type)
        code = f.cpt or "the claim"
        points.append(
            f"{ftype.replace('_', ' ')} on {code}: ${round(f.dollar_impact, 2):,.2f} "
            f"(derived flag)")
    t = report.get("totals", {})
    if t.get("medicare_multiple"):
        points.append(
            f"Billed total ${t['billed']:,.2f} is {t['medicare_multiple']}x the Medicare "
            f"rate of ${t['medicare']:,.2f} (benchmark anchor).")
    rand_lines = [ln["code"] for ln in report.get("lines", []) if ln.get("rand_flag")]
    if rand_lines:
        points.append(
            f"Lines {', '.join(rand_lines)} are billed above the commercial (RAND-norm) "
            f"ceiling — quantified overcharges (benchmark anchor).")
    return points


def build_answer_key(sc: dict, flags, report: dict) -> dict:
    return {
        "scenario_id": sc["id"],
        "expected_flags": serialize_flags(flags),
        "benchmark_report": report,
        "ask": build_ask(report),
        "call_talking_points": build_talking_points(flags, report),
        "provenance": dict(PROVENANCE_STATIC),
    }


# ── artifact serialization ────────────────────────────────────────────────
def _dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _scenario_json(sc: dict) -> dict:
    hk = sc["hospital_key"]
    if hk:
        h = HOSPITALS[hk]
        hospital = {"name": h["name"], "ein": h["ein"], "ccn": h["ccn"],
                    "city": h["city"], "state": h["state"]}
    else:
        hospital = {"name": sc["spec"]["bill"]["facility_name"], "ein": None,
                    "ccn": None, "city": "Boston", "state": "MA"}
    return {
        "scenario_id": sc["id"],
        "archetype": sc["archetype"],
        "title": sc["title"],
        "narrative": sc["narrative"],
        "hospital": hospital,
        "patient": sc["patient"],
        "coverage": sc["coverage"],
        "provider_entities": [{"name": e["name"], "entity_type": e["entity_type"]}
                              for e in sc["provider_entities"]],
        "service_date": sc["service_date"],
        "answer_key_ref": "answer_key.json",
    }


def _bill_pdf_ctx(sc: dict) -> dict:
    hk = sc["hospital_key"]
    h = HOSPITALS[hk] if hk else {"name": sc["spec"]["bill"]["facility_name"],
                                  "ein": "04-0000000", "ccn": "220000",
                                  "address": "Boston, MA"}
    bill = sc["spec"]["bill"]
    cov = sc["coverage"]
    payer = cov.get("payer_name") or "Self-pay (uninsured)"
    total = round(sum(li["billed_amount"] for li in bill["line_items"]), 2)
    ins_paid = round(total - bill["patient_balance"], 2)
    return {
        "hospital_name": h["name"], "address": h["address"], "tax_id": h["ein"],
        "ccn": h["ccn"], "patient": sc["patient"]["name"], "dob": sc["patient"]["dob"],
        "account": sc["patient"]["account_number"], "dos": sc["service_date"],
        "statement_date": bill.get("statement_date", ""), "due_date": bill.get("due_date", ""),
        "payer": payer, "diagnosis": sc["diagnosis"], "lines": bill["line_items"],
        "total_billed": total, "insurance_paid": ins_paid if ins_paid > 0 else 0.0,
        "balance": bill["patient_balance"],
    }


def _eob_pdf_ctx(sc: dict) -> dict | None:
    eob = sc["spec"]["eob"]
    if not eob or eob.get("patient_responsibility_total") is None:
        return None
    cov = sc["coverage"]
    remark = None
    if sc["archetype"] == "denial_driven":
        remark = ("CPT 70450 denied - denial code 197: prior authorization/precertification "
                  "absent. You may appeal within 180 days.")
    elif sc["archetype"] == "oon_balance_bill":
        remark = ("Anesthesia was out-of-network. Under the No Surprises Act your cost share "
                  "is limited to the in-network amount; balances above it may be disputed.")
    elif sc["archetype"] == "eob_mismatch":
        remark = ("Allowed amounts reflect your plan's contracted rate. You should not be billed "
                  "above the patient responsibility shown here.")
    return {
        "payer": cov["payer_name"], "payer_address": "P.O. Box 9100, Boston, MA 02205",
        "member": sc["patient"]["name"], "member_id": cov.get("member_id") or "",
        "group": cov.get("plan_name") or "", "claim": eob.get("claim_number") or "",
        "date_processed": sc["service_date"], "provider": sc["spec"]["bill"]["facility_name"],
        "dos": sc["service_date"], "lines": eob.get("line_items") or [],
        "eob_billed": round(sum((li.get("billed_amount") or 0) for li in eob.get("line_items") or []), 2),
        "eob_plan_paid": round(sum((li.get("plan_paid") or 0) for li in eob.get("line_items") or []), 2),
        "eob_resp": eob["patient_responsibility_total"], "remark": remark,
    }


def _artifacts_for(sc: dict, flags, report: dict) -> dict[str, bytes]:
    """All files for one scenario, path(relative) -> bytes."""
    files: dict[str, bytes] = {}
    files["scenario.json"] = _dumps(_scenario_json(sc)).encode("utf-8")
    files["job_spec.json"] = _dumps(sc["spec"]).encode("utf-8")
    files["bill.json"] = _dumps(sc["spec"]["bill"]).encode("utf-8")
    eob = sc["spec"]["eob"]
    if eob and (eob.get("patient_responsibility_total") is not None or eob.get("line_items")):
        files["eob.json"] = _dumps(eob).encode("utf-8")
    files["answer_key.json"] = _dumps(build_answer_key(sc, flags, report)).encode("utf-8")
    files["bill.pdf"] = render_scenario_bill_pdf(_bill_pdf_ctx(sc))
    eob_ctx = _eob_pdf_ctx(sc)
    if eob_ctx is not None:
        files["eob.pdf"] = render_scenario_eob_pdf(eob_ctx)
    return files


def generate(check: bool = False) -> int:
    config = load_vertical()
    ncci = load_ncci_table(config)
    lookup = build_scenario_lookup()
    scenarios = scenario_definitions(lookup)

    drift: list[str] = []
    for sc in scenarios:
        flags, report = run_pipeline(sc["spec"], lookup, config, ncci)
        files = _artifacts_for(sc, flags, report)
        sc_dir = SCENARIOS_DIR / sc["id"]
        # scenario dirs may legitimately have a stale eob.{json,pdf} (e.g. an
        # archetype that dropped its EOB) — prune those on a full write.
        expected = set(files)
        if check:
            for name, data in files.items():
                path = sc_dir / name
                if not path.exists() or path.read_bytes() != data:
                    drift.append(f"{sc['id']}/{name}")
        else:
            sc_dir.mkdir(parents=True, exist_ok=True)
            for name, data in files.items():
                (sc_dir / name).write_bytes(data)
            for stale in ("eob.json", "eob.pdf"):
                if stale not in expected and (sc_dir / stale).exists():
                    (sc_dir / stale).unlink()
        flag_summary = ", ".join(f"{f.type}:{f.dollar_impact}" for f in flags) or "(none)"
        print(f"{'CHECK' if check else 'WROTE'} {sc['id']:24s} flags=[{flag_summary}]")

    if check and drift:
        print("\nDRIFT DETECTED (regenerate with `python data/scenarios/generate.py`):")
        for d in drift:
            print(f"  - {d}")
        return 1
    print(f"\n{'All 9 scenarios byte-identical.' if check else 'Wrote 9 scenarios.'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the WS4 scenario suite.")
    ap.add_argument("--check", action="store_true",
                    help="verify committed artifacts are byte-identical; exit 1 on drift")
    args = ap.parse_args()
    return generate(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
