"""Estimator endpoints — case + JobSpec + report.

Persistence is best-effort (app/db.py no-ops without a DB); the fixture cases
(Maya/Dan/Nina, app/fixtures_users.py) keep serving either way. TODO(J): plug
parse_documents into the OpenAI vision extraction prompt
(data/pipeline/extraction_prompt.md).
"""
from fastapi import APIRouter, HTTPException

from .. import db, storage
from ..action_plan_copy import generate_action_plan_copy
from ..config import load_vertical
from ..engine.action_plan import build_action_plan_input
from ..engine.report import build_lines, build_recommendation, fair_total, rank_outcomes
from ..fixtures import DEMO_JOB_SPEC, demo_benchmarks
from ..fixtures_users import OWNER_EMAIL_BY_CASE_ID, flags_for_spec, spec_for_case, spec_for_email
from ..models import JobSpec

router = APIRouter()


def _resolve_spec(case_id: str) -> dict:
    spec = spec_for_case(case_id)
    if spec is None:
        raise HTTPException(404, "case not found (only the fixture cases exist so far)")
    return spec


@router.get("/demo", response_model=JobSpec)
def get_demo_case() -> dict:
    """Maya's fixture case — lets web + agents integrate before parsing exists."""
    return DEMO_JOB_SPEC


@router.get("/mine", response_model=JobSpec)
def get_my_case(email: str | None = None) -> dict:
    """The logged-in user's case: cases.owner_email match first (live DB), then
    the email→fixture registry, then Maya's demo case (logged-out default)."""
    if email:
        row = db.get_case_by_owner_email(email.strip().lower())
        if row is not None:
            spec = spec_for_case(str(row["id"]))
            if spec is not None:
                return spec
        spec = spec_for_email(email)
        if spec is not None:
            return spec
    return DEMO_JOB_SPEC


@router.get("/{case_id}", response_model=JobSpec)
def get_case(case_id: str) -> dict:
    return _resolve_spec(case_id)


@router.get("/{case_id}/flags")
def get_case_flags(case_id: str) -> dict:
    """Red flags computed live by the deterministic engine (PRD §7)."""
    spec = _resolve_spec(case_id)
    return {"case_id": case_id, "flags": [f.model_dump() for f in flags_for_spec(spec)]}


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
    spec = _resolve_spec(case_id)
    real_id = spec["case_id"]
    db.ensure_case(real_id, spec, OWNER_EMAIL_BY_CASE_ID.get(real_id))
    db.set_case_status(real_id, "confirmed")
    return {"case_id": case_id, "status": "confirmed"}


@router.get("/{case_id}/report")
def get_case_report(case_id: str) -> dict:
    """Ranked outcomes + per-CPT lines + a data-built recommendation (no LLM)."""
    spec_dict = _resolve_spec(case_id)
    spec = JobSpec.model_validate(spec_dict)
    flags, benchmarks = flags_for_spec(spec_dict), demo_benchmarks()

    outcomes = db.get_case_outcomes(spec_dict["case_id"]) or []
    ranked = rank_outcomes(outcomes, fair_total(spec, flags, benchmarks))
    for o in ranked:  # frozen contract: entity + evidence events + recording_url
        o["entity"] = o.get("target_entity")
        # resolved_at: when the outcome was reached = when its call ended. Lets the
        # case view date each paper-trail entry without a new column.
        o["resolved_at"] = o.pop("ended_at", None)
        events = db.get_events_by_ids(o.get("evidence_event_ids") or []) or []
        o["evidence"] = [{"ts": e.get("ts"), "type": e.get("type"), "payload": e.get("payload")}
                         for e in events]
        path = o.pop("recording_path", None)
        o["recording_url"] = storage.sign_url(path) if path else None
    # The per-CPT lines table describes the FACILITY's bill, so only a
    # settlement with the facility may fill its "achieved" column. Accuracy
    # audit finding: the first monetary outcome used to leak in regardless of
    # entity, spreading a collections settlement across the hospital's lines.
    facility = spec.bill.facility_name
    best_final = next(
        (float(o["final_amount"]) for o in ranked
         if o.get("final_amount") is not None and o.get("entity") == facility),
        None,
    )
    return {
        "case_id": case_id,
        "outcomes": ranked,
        "lines": build_lines(spec, flags, benchmarks, best_final),
        "recommendation": build_recommendation(ranked),
        # The case's own identifiers, so the patient can read them aloud on a
        # call (surfaced as copyable reference chips in the case view header).
        "account_number": spec.bill.account_number,
        "claim_number": spec.eob.claim_number,
    }
