"""Per-user demo fixtures — Dan's and Nina's cases beside Maya's (app/fixtures.py).

Three demo logins, three different stories the same engine handles:
  maya@hagglfor.me  the flagship 4-flag hospital negotiation (fixtures.DEMO_JOB_SPEC)
  dan@hagglfor.me   collections-only: an older for-profit urgent-care bill sold to
                    Meridian Recovery Services — duplicate + markup flags, route
                    "collections", floor $900
  nina@hagglfor.me  No Surprises Act: emergency visit at an in-network nonprofit
                    hospital, balance-billed $3,120 by out-of-network anesthesia —
                    the thresholds.nsa_do_not_negotiate path (cite the statute and
                    file a complaint, never haggle the protected balance)

Numbers reconcile with data/seed/benchmarks_v0.json; the arithmetic each amount
encodes is asserted in apps/api/tests/test_fixtures_users.py.
"""
from .fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC

DAN_CASE_ID = "00000000-0000-0000-0000-000000000002"
NINA_CASE_ID = "00000000-0000-0000-0000-000000000003"

MAYA_EMAIL = "maya@hagglfor.me"
DAN_EMAIL = "dan@hagglfor.me"
NINA_EMAIL = "nina@hagglfor.me"

# ── Dan — $2,140 older bill, sold to collections ──────────────────────────
# Line arithmetic (engine-verified in tests):
#   duplicate  71046 billed twice @ $380 same date → impact $380
#   markup     96374 @ $520 > band_high $261.75 → impact $258.25
#   99283 @ $600 ≤ band_high $612.50, 80053 @ $35 ≤ $36.25, 85025 @ $25 ≤ $27
#   (no markup); 93005 has no benchmark row. Lines sum to the $2,140 balance.
#   No EOB (self-pay at time of service) → no eob_mismatch.
_DAN_DOS = "2025-09-14"
DAN_LINE_ITEMS: list[dict] = [
    {"cpt": "99283", "description": "Emergency dept visit, moderate severity",
     "date_of_service": _DAN_DOS, "billed_amount": 600.00, "dx_codes": ["J06.9"]},
    {"cpt": "71046", "description": "Chest X-ray, 2 views", "date_of_service": _DAN_DOS, "billed_amount": 380.00},
    {"cpt": "71046", "description": "Chest X-ray, 2 views", "date_of_service": _DAN_DOS, "billed_amount": 380.00},
    {"cpt": "96374", "description": "IV push, single drug", "date_of_service": _DAN_DOS, "billed_amount": 520.00},
    {"cpt": "80053", "description": "Comprehensive metabolic panel", "date_of_service": _DAN_DOS, "billed_amount": 35.00},
    {"cpt": "85025", "description": "Complete blood count w/ differential", "date_of_service": _DAN_DOS, "billed_amount": 25.00},
    {"cpt": "93005", "description": "Electrocardiogram, tracing only", "date_of_service": _DAN_DOS, "billed_amount": 200.00},
]

DAN_JOB_SPEC: dict = {
    "case_id": DAN_CASE_ID,
    "patient": {"legal_name": "Dan Kowalski", "dob": "1987-11-02"},
    "insurance": {"payer_name": "Self-pay (uninsured at time of service)"},
    "financial_profile": {
        "household_income": 70000,
        "household_size": 1,
        "fpl_percent": 450,
        "employment_status": "employed_full_time",
        "lump_sum_available": 900,
        "max_monthly_payment": 100,
    },
    "authorizations": {"hipaa_roi": "confirmed", "recording_consent": "confirmed"},
    "bill": {
        "facility_name": "Riverside Urgent Care",   # for-profit — no 501(r) lever
        "nonprofit_status": False,
        "statement_date": "2025-10-05",
        "due_date": "2025-11-04",
        "account_number": "RUC-2210441",
        "is_itemized": True,
        "total_billed": 2140.00,
        "patient_balance": 2140.00,
        "line_items": DAN_LINE_ITEMS,
    },
    "eob": {"claim_number": None, "patient_responsibility_total": None, "denial_codes": [], "line_items": []},
    "derived_flags": [
        {"type": "duplicate", "cpt": "71046", "evidence": {"dates": [_DAN_DOS, _DAN_DOS]}, "dollar_impact": 380.00},
        {"type": "markup", "cpt": "96374", "evidence": {"billed": 520.00, "band_high": 261.75, "threshold": 261.75},
         "dollar_impact": 258.25},
    ],
    "entities": [
        {"name": "Meridian Recovery Services", "kind": "collections", "balance": 2140.00},
    ],
}

# ── Nina — No Surprises Act balance bill ──────────────────────────────────
# Emergency visit at an in-network nonprofit hospital; the out-of-network
# anesthesia group balance-bills $3,120 while the EOB puts her in-network
# share at $850 → eob_mismatch $2,270 (engine-computed) and a seeded `nsa`
# flag for the same protected amount. Per thresholds.nsa_do_not_negotiate the
# play is cite_statute_and_file_complaint — not a negotiation ladder.
_NINA_DOS = "2026-06-15"
NINA_JOB_SPEC: dict = {
    "case_id": NINA_CASE_ID,
    "patient": {"legal_name": "Nina Osei", "dob": "1992-04-27"},
    "insurance": {"payer_name": "Harvard Pilgrim Health Care", "member_id": "HP-77120394", "plan_type": "HMO"},
    "financial_profile": {
        "household_income": 50000,
        "household_size": 1,
        "fpl_percent": 320,
        "employment_status": "employed_full_time",
        "lump_sum_available": 800,
        "max_monthly_payment": 120,
    },
    "authorizations": {"hipaa_roi": "confirmed", "recording_consent": "confirmed"},
    "bill": {
        "facility_name": "Commonwealth Anesthesia Associates",
        "nonprofit_status": True,                    # nonprofit system — 501(r) lever stays armed
        "statement_date": "2026-06-28",
        "due_date": "2026-07-28",
        "account_number": "CAA-2026-8841",
        "is_itemized": True,
        "total_billed": 3120.00,
        "patient_balance": 3120.00,
        "line_items": [
            {"cpt": "00840", "description": "Anesthesia, emergency abdominal surgery (out-of-network)",
             "date_of_service": _NINA_DOS, "billed_amount": 3120.00},
        ],
    },
    "eob": {
        "claim_number": "HPHC-2026-55871",
        "patient_responsibility_total": 850.00,
        "denial_codes": [],
        "line_items": [],
    },
    "derived_flags": [
        {"type": "nsa", "cpt": "00840",
         "evidence": {"emergency": True, "facility_network_status": "in_network",
                      "provider_network_status": "out_of_network", "statute": "No Surprises Act"},
         "dollar_impact": 2270.00},
        {"type": "eob_mismatch", "cpt": None, "evidence": {"bill": 3120.00, "eob": 850.00}, "dollar_impact": 2270.00},
    ],
    "entities": [
        {"name": "Boston Harbor Medical Center", "kind": "facility", "balance": 0.00},
        {"name": "Commonwealth Anesthesia Associates", "kind": "anesthesia", "balance": 3120.00},
    ],
}

# ── email → fixture registry (GET /cases/mine + per-case serving) ─────────
SPEC_BY_EMAIL: dict[str, dict] = {
    MAYA_EMAIL: DEMO_JOB_SPEC,
    DAN_EMAIL: DAN_JOB_SPEC,
    NINA_EMAIL: NINA_JOB_SPEC,
}

SPEC_BY_CASE_ID: dict[str, dict] = {
    DEMO_CASE_ID: DEMO_JOB_SPEC,
    DAN_CASE_ID: DAN_JOB_SPEC,
    NINA_CASE_ID: NINA_JOB_SPEC,
}

OWNER_EMAIL_BY_CASE_ID: dict[str, str] = {
    DEMO_CASE_ID: MAYA_EMAIL,
    DAN_CASE_ID: DAN_EMAIL,
    NINA_CASE_ID: NINA_EMAIL,
}


def spec_for_email(email: str | None) -> dict | None:
    return SPEC_BY_EMAIL.get((email or "").strip().lower())


def spec_for_case(case_id: str) -> dict | None:
    if case_id == "demo":
        return DEMO_JOB_SPEC
    return SPEC_BY_CASE_ID.get(case_id)


def flags_for_spec(spec_dict: dict) -> list:
    """Engine-computed flags for a fixture spec (the demo keeps its cached path).
    Lazy imports mirror fixtures.py so importing this module stays cheap."""
    from .config import load_vertical
    from .engine.flags import detect_flags
    from .fixtures import demo_benchmarks, demo_flags
    from .models import JobSpec

    if spec_dict is DEMO_JOB_SPEC:
        return demo_flags()
    return detect_flags(JobSpec.model_validate(spec_dict), load_vertical(), demo_benchmarks())
