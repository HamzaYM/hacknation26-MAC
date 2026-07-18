"""Test fixtures for the engine.

The demo bill's line items live in app.fixtures.DEMO_LINE_ITEMS (the API
serves them, so they can't live only under tests/) and are re-exported here.
NOTE: J's parsed-PDF output (E3) must eventually match DEMO_LINE_ITEMS
exactly — codes, dates, amounts — or the seeded flags stop reconciling with
data/seed/demo_answer_key.json.

CLEAN_LINE_ITEMS is a bill with zero findables — the false-positive guard:
  · 71046 twice but on DIFFERENT dates (not a duplicate)
  · 36415 twice same date but $12 each (extra $12 < duplicate min_amount $25)
  · 99283 with the low-acuity dx (not an em_pairs billed code → no upcode)
  · 80053 billed AS the bundle (no unbundle)
  · every benchmarked line within its fair band (no markup)
  · patient_balance == EOB patient responsibility (no eob_mismatch)
"""
import copy

from app.fixtures import DEMO_JOB_SPEC, DEMO_LINE_ITEMS  # noqa: F401  (re-export)
from app.models import JobSpec

CLEAN_LINE_ITEMS: list[dict] = [
    {"cpt": "99283", "description": "ED visit, moderate severity", "date_of_service": "2026-06-02",
     "billed_amount": 550.00, "dx_codes": ["J06.9"]},
    {"cpt": "71046", "description": "Chest X-ray, 2 views", "date_of_service": "2026-06-02", "billed_amount": 150.00},
    {"cpt": "71046", "description": "Chest X-ray, 2 views", "date_of_service": "2026-06-03", "billed_amount": 150.00},
    {"cpt": "36415", "description": "Venipuncture", "date_of_service": "2026-06-02", "billed_amount": 12.00},
    {"cpt": "36415", "description": "Venipuncture", "date_of_service": "2026-06-02", "billed_amount": 12.00},
    {"cpt": "80053", "description": "Comprehensive metabolic panel", "date_of_service": "2026-06-02", "billed_amount": 30.00},
    {"cpt": "85025", "description": "CBC w/ differential", "date_of_service": "2026-06-02", "billed_amount": 25.00},
    {"cpt": "96374", "description": "IV push, single drug", "date_of_service": "2026-06-02", "billed_amount": 250.00},
]


def demo_job_spec() -> JobSpec:
    return JobSpec.model_validate(DEMO_JOB_SPEC)


def clean_job_spec() -> JobSpec:
    """The demo case with a findable-free bill and a reconciled EOB."""
    raw = copy.deepcopy(DEMO_JOB_SPEC)
    raw["bill"]["line_items"] = CLEAN_LINE_ITEMS
    total = round(sum(li["billed_amount"] for li in CLEAN_LINE_ITEMS), 2)
    raw["bill"]["total_billed"] = total
    raw["bill"]["patient_balance"] = total
    raw["eob"]["patient_responsibility_total"] = total
    raw["derived_flags"] = []
    return JobSpec.model_validate(raw)
