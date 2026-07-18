"""Fixture data so the whole stack runs before real parsing/calls exist.

The demo case is Maya's (PRD §3/§10.3). Numbers MUST stay reconciled with
data/seed/benchmarks_v0.json and data/seed/demo_answer_key.json.
"""
import json

from .config import SEED_DIR

DEMO_CASE_ID = "00000000-0000-0000-0000-000000000001"


def demo_benchmarks() -> dict[str, dict]:
    with open(SEED_DIR / "benchmarks_v0.json") as f:
        rows = json.load(f)
    return {r["cpt"]: r for r in rows}


DEMO_JOB_SPEC: dict = {
    "case_id": DEMO_CASE_ID,
    "patient": {"legal_name": "Maya Chen", "dob": "1995-03-14"},
    "insurance": {"payer_name": "BlueCross NC", "member_id": "XYZ123456", "plan_type": "PPO"},
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
        "line_items": [],            # populated by the parser (E3) from the synthetic PDF
    },
    "eob": {
        "claim_number": "BCNC-2026-118842",
        "patient_responsibility_total": 3875.00,
        "denial_codes": [],
        "line_items": [],
    },
    "derived_flags": [
        {"type": "duplicate", "cpt": "71046", "evidence": {"dates": ["2026-06-02", "2026-06-02"]}, "dollar_impact": 412.00},
        {"type": "upcode", "cpt": "99285", "evidence": {"supported": "99283"}, "dollar_impact": 890.00},
        {"type": "unbundle", "cpt": "80053", "evidence": {"components_billed": 690.00, "bundled": 48.00}, "dollar_impact": 642.00},
        {"type": "eob_mismatch", "cpt": None, "evidence": {"bill": 4287.00, "eob": 3875.00}, "dollar_impact": 412.00},
    ],
    "entities": [
        {"name": "Mercy General Hospital", "kind": "facility", "balance": 4287.00},
        {"name": "Carolina Emergency Physicians", "kind": "er_physician_group", "balance": 640.00},
        {"name": "Meridian Recovery Services", "kind": "collections", "balance": 980.00},
    ],
}
