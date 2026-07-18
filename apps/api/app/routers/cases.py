"""Estimator endpoints — case + JobSpec.

TODO(Hamza): wire Supabase persistence; TODO(J): plug parse_documents into the
OpenAI vision extraction prompt (data/pipeline/extraction_prompt.md).
"""
from fastapi import APIRouter, HTTPException

from ..fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC, demo_flags
from ..models import JobSpec

router = APIRouter()


@router.get("/demo", response_model=JobSpec)
def get_demo_case() -> dict:
    """Maya's fixture case — lets web + agents integrate before parsing exists."""
    return DEMO_JOB_SPEC


@router.get("/{case_id}", response_model=JobSpec)
def get_case(case_id: str) -> dict:
    if case_id in (DEMO_CASE_ID, "demo"):
        return DEMO_JOB_SPEC
    raise HTTPException(404, "case not found (only the demo fixture exists so far)")


@router.get("/{case_id}/flags")
def get_case_flags(case_id: str) -> dict:
    """Red flags computed live by the deterministic engine (PRD §7)."""
    if case_id not in (DEMO_CASE_ID, "demo"):
        raise HTTPException(404, "case not found (only the demo fixture exists so far)")
    return {"case_id": case_id, "flags": [f.model_dump() for f in demo_flags()]}


@router.post("/{case_id}/confirm")
def confirm_spec(case_id: str) -> dict:
    """The challenge-mandated gate: nothing dials until the user confirms the spec."""
    # TODO(Hamza): persist status=confirmed; freeze the JobSpec snapshot used verbatim in calls
    return {"case_id": case_id, "status": "confirmed"}
