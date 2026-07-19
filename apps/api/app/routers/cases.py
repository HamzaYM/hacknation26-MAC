"""Estimator endpoints — case + JobSpec + report.

Persistence is best-effort (app/db.py no-ops without a DB); the demo fixture
keeps serving either way. TODO(J): plug parse_documents into the OpenAI vision
extraction prompt (data/pipeline/extraction_prompt.md).
"""
from fastapi import APIRouter, HTTPException

from .. import db, storage
from ..action_plan_copy import generate_action_plan_copy
from ..config import load_vertical
from ..engine.action_plan import build_action_plan_input
from ..engine.report import build_lines, build_recommendation, fair_total, rank_outcomes
from ..fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC, demo_benchmarks, demo_flags
from ..models import JobSpec

router = APIRouter()


def _require_demo(case_id: str) -> None:
    if case_id not in (DEMO_CASE_ID, "demo"):
        raise HTTPException(404, "case not found (only the demo fixture exists so far)")


@router.get("/demo", response_model=JobSpec)
def get_demo_case() -> dict:
    """Maya's fixture case — lets web + agents integrate before parsing exists."""
    return DEMO_JOB_SPEC


@router.get("/{case_id}", response_model=JobSpec)
def get_case(case_id: str) -> dict:
    _require_demo(case_id)
    return DEMO_JOB_SPEC


@router.get("/{case_id}/flags")
def get_case_flags(case_id: str) -> dict:
    """Red flags computed live by the deterministic engine (PRD §7)."""
    _require_demo(case_id)
    return {"case_id": case_id, "flags": [f.model_dump() for f in demo_flags()]}


@router.get("/{case_id}/action_plan")
def get_case_action_plan(case_id: str, no_llm: bool = False) -> dict:
    """The pre-dial Action Plan for the /confirm screen (PRD §11 screen 3).

    `input` is the code-computed payload (every number/date/statute from the
    engine + J's config/levers.json — PRD §7). `copy` is the user-facing text:
    warm `claude -p` prose when available and honest, deterministic fallback
    otherwise. Pass ?no_llm=true to force the fallback (used for fast demos/tests).
    """
    _require_demo(case_id)
    spec = JobSpec.model_validate(DEMO_JOB_SPEC)
    flags, benchmarks = demo_flags(), demo_benchmarks()
    payload = build_action_plan_input(spec, flags, benchmarks, load_vertical())
    copy = generate_action_plan_copy(payload, use_llm=not no_llm)
    return {"case_id": case_id, "input": payload, "copy": copy}


@router.post("/{case_id}/confirm")
def confirm_spec(case_id: str) -> dict:
    """The challenge-mandated gate: nothing dials until the user confirms the spec."""
    _require_demo(case_id)
    db.ensure_demo_case()
    db.set_case_status(DEMO_CASE_ID, "confirmed")
    return {"case_id": case_id, "status": "confirmed"}


@router.get("/{case_id}/report")
def get_case_report(case_id: str) -> dict:
    """Ranked outcomes + per-CPT lines + a data-built recommendation (no LLM)."""
    _require_demo(case_id)
    spec = JobSpec.model_validate(DEMO_JOB_SPEC)
    flags, benchmarks = demo_flags(), demo_benchmarks()

    outcomes = db.get_case_outcomes(DEMO_CASE_ID) or []
    ranked = rank_outcomes(outcomes, fair_total(spec, flags, benchmarks))
    for o in ranked:  # frozen contract: entity + evidence events + recording_url
        o["entity"] = o.get("target_entity")
        events = db.get_events_by_ids(o.get("evidence_event_ids") or []) or []
        o["evidence"] = [{"ts": e.get("ts"), "type": e.get("type"), "payload": e.get("payload")}
                         for e in events]
        path = o.pop("recording_path", None)
        o["recording_url"] = storage.sign_url(path) if path else None
    best_final = next(
        (float(o["final_amount"]) for o in ranked if o.get("final_amount") is not None), None
    )
    return {
        "case_id": case_id,
        "outcomes": ranked,
        "lines": build_lines(spec, flags, benchmarks, best_final),
        "recommendation": build_recommendation(ranked),
    }
