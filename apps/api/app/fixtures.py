"""Fixture data so the whole stack runs before real parsing/calls exist.

The demo case is Maya's (PRD §3/§10.3). Numbers MUST stay reconciled with
data/seed/benchmarks_v0.json and data/seed/demo_answer_key.json.
"""
import json
from functools import lru_cache

from .config import SEED_DIR, load_vertical

DEMO_CASE_ID = "00000000-0000-0000-0000-000000000001"


def demo_benchmarks() -> dict[str, dict]:
    with open(SEED_DIR / "benchmarks_v0.json") as f:
        rows = json.load(f)
    return {r["cpt"]: r for r in rows}


# ── Demo bill line items (derived from demo_answer_key.json + benchmarks) ──
# J's parsed PDF output (E3) MUST eventually match this list exactly — codes,
# dates, and amounts — or the seeded flags stop reconciling with the answer key.
# The arithmetic each amount encodes is documented in apps/api/tests/test_flags.py.
# Lines sum to the $8,432 statement total.
_DOS = "2026-06-02"
DEMO_LINE_ITEMS: list[dict] = [
    # (b) upcode candidate: level-5 E/M with a low-acuity dx (J06.9, acute URI);
    #     impact = 2340 - mrf_negotiated_median(99283)=328.79 → $2011.21
    {"cpt": "99285", "description": "Emergency department visit, high severity (level 5)",
     "date_of_service": _DOS, "billed_amount": 2340.00, "dx_codes": ["J06.9"]},
    # (a) duplicate: chest X-ray billed twice same date → impact $412
    {"cpt": "71046", "description": "Chest X-ray, 2 views", "date_of_service": _DOS, "billed_amount": 412.00},
    {"cpt": "71046", "description": "Chest X-ray, 2 views", "date_of_service": _DOS, "billed_amount": 412.00},
    # (c) unbundle: all 14 CMP components billed instead of 80053 —
    #     components total $690, bundled price $48 → impact $642
    {"cpt": "84295", "description": "Sodium", "date_of_service": _DOS, "billed_amount": 50.00},
    {"cpt": "84132", "description": "Potassium", "date_of_service": _DOS, "billed_amount": 50.00},
    {"cpt": "82374", "description": "Carbon dioxide", "date_of_service": _DOS, "billed_amount": 45.00},
    {"cpt": "82435", "description": "Chloride", "date_of_service": _DOS, "billed_amount": 45.00},
    {"cpt": "82947", "description": "Glucose", "date_of_service": _DOS, "billed_amount": 50.00},
    {"cpt": "82565", "description": "Creatinine", "date_of_service": _DOS, "billed_amount": 52.00},
    {"cpt": "84520", "description": "Urea nitrogen (BUN)", "date_of_service": _DOS, "billed_amount": 50.00},
    {"cpt": "82310", "description": "Calcium", "date_of_service": _DOS, "billed_amount": 52.00},
    {"cpt": "84075", "description": "Alkaline phosphatase", "date_of_service": _DOS, "billed_amount": 55.00},
    {"cpt": "84155", "description": "Protein, total", "date_of_service": _DOS, "billed_amount": 50.00},
    {"cpt": "84450", "description": "Transferase, AST", "date_of_service": _DOS, "billed_amount": 52.00},
    {"cpt": "84460", "description": "Transferase, ALT", "date_of_service": _DOS, "billed_amount": 52.00},
    {"cpt": "82040", "description": "Albumin", "date_of_service": _DOS, "billed_amount": 47.00},
    {"cpt": "82247", "description": "Bilirubin, total", "date_of_service": _DOS, "billed_amount": 40.00},
    # clean lines, billed within the fair band (no markup flag)
    {"cpt": "85025", "description": "Complete blood count w/ differential", "date_of_service": _DOS, "billed_amount": 24.00},
    {"cpt": "96374", "description": "IV push, single drug", "date_of_service": _DOS, "billed_amount": 210.00},
    # clean lines with no benchmark row (markup rule skips them)
    {"cpt": "93005", "description": "Electrocardiogram, tracing only", "date_of_service": _DOS, "billed_amount": 1364.00},
    {"cpt": "96361", "description": "IV hydration, each additional hour", "date_of_service": _DOS, "billed_amount": 1120.00},
    {"cpt": "J7030", "description": "Normal saline solution, 1000 cc", "date_of_service": _DOS, "billed_amount": 980.00},
    {"cpt": "J2405", "description": "Ondansetron HCl injection, 4 mg", "date_of_service": _DOS, "billed_amount": 880.00},
]

DEMO_JOB_SPEC: dict = {
    "case_id": DEMO_CASE_ID,
    "patient": {"legal_name": "Maya Chen", "dob": "1995-03-14"},
    "insurance": {"payer_name": "Blue Cross Blue Shield of Massachusetts", "member_id": "XYZ123456", "plan_type": "PPO"},
    "financial_profile": {
        "household_income": 39000,
        "household_size": 2,
        "fpl_percent": 250,          # computed by code from income + size
        "employment_status": "employed_part_time",
        "lump_sum_available": 1700,
        "max_monthly_payment": 150,
    },
    "authorizations": {"hipaa_roi": "confirmed", "recording_consent": "confirmed"},
    "bill": {
        "facility_name": "Mercy General Hospital",
        "nonprofit_status": True,
        "statement_date": "2026-06-20",
        "due_date": "2026-07-20",
        "account_number": "MG-4471983",
        "is_itemized": True,
        "total_billed": 8432.00,
        "patient_balance": 4287.00,
        "line_items": DEMO_LINE_ITEMS,   # J's parser (E3) must reproduce these from the PDF
    },
    "eob": {
        "claim_number": "BCNC-2026-118842",
        "patient_responsibility_total": 3875.00,
        "denial_codes": [],
        "line_items": [],
    },
    "derived_flags": [
        {"type": "duplicate", "cpt": "71046", "evidence": {"dates": ["2026-06-02", "2026-06-02"]}, "dollar_impact": 412.00},
        {"type": "upcode", "cpt": "99285", "evidence": {"supported": "99283"}, "dollar_impact": 2011.21},
        {"type": "unbundle", "cpt": "80053", "evidence": {"components_billed": 690.00, "bundled": 48.00}, "dollar_impact": 642.00},
        {"type": "eob_mismatch", "cpt": None, "evidence": {"bill": 4287.00, "eob": 3875.00}, "dollar_impact": 412.00},
    ],
    "entities": [
        {"name": "Mercy General Hospital", "kind": "facility", "balance": 4287.00},
        {"name": "Bay State Emergency Physicians", "kind": "er_physician_group", "balance": 640.00},
        {"name": "Meridian Recovery Services", "kind": "collections", "balance": 980.00},
    ],
}


# ── Engine-derived demo objects (computed, cached; must equal the seeds) ──
@lru_cache
def demo_flags() -> list:
    """Red flags computed by the engine over the fixture bill (list[DerivedFlag])."""
    from .engine.flags import detect_flags
    from .models import JobSpec

    return detect_flags(JobSpec.model_validate(DEMO_JOB_SPEC), load_vertical(), demo_benchmarks())


@lru_cache
def demo_dossier():
    """StrategyDossier for the demo's primary target (Mercy General, provider route)."""
    from .engine.dossier import build_dossier
    from .models import JobSpec

    spec = JobSpec.model_validate(DEMO_JOB_SPEC)
    return build_dossier(spec, demo_flags(), demo_benchmarks(), load_vertical(), entity=spec.entities[0])
