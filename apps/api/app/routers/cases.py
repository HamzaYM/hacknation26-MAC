"""Estimator endpoints — case + JobSpec + report.

Persistence is best-effort (app/db.py no-ops without a DB); the fixture cases
(Maya/Dan/Nina, app/fixtures_users.py) keep serving either way. TODO(J): plug
parse_documents into the OpenAI vision extraction prompt
(data/pipeline/extraction_prompt.md).
"""
import uuid as uuidlib

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from .. import case_store, db, storage
from ..action_plan_copy import generate_action_plan_copy
from ..config import load_vertical
from ..engine.action_plan import build_action_plan_input
from ..engine.dossier import build_dossier
from ..engine.report import build_lines, build_recommendation, fair_total, rank_outcomes
from ..fixtures import DEMO_JOB_SPEC, demo_benchmarks
from ..fixtures_users import OWNER_EMAIL_BY_CASE_ID, flags_for_spec, spec_for_case, spec_for_email
from ..models import JobSpec

router = APIRouter()


def _resolve_spec(case_id: str) -> dict:
    """Fixture cases (Maya/Dan/Nina + email registry) first — unchanged
    behavior. Any OTHER case_id falls through to case_store: cases created via
    POST /cases or a scenario load (case_store.SLOTS: job_spec/flags/
    benchmark_report/dossier/allowed_numbers/scenario_id/answer_key)."""
    spec = spec_for_case(case_id)
    if spec is None:
        spec = case_store.get_job_spec(case_id)
    if spec is None:
        raise HTTPException(404, "case not found")
    return spec


class CreateCaseRequest(BaseModel):
    """JobSpec-shaped body (contracts/job_spec.schema.json). case_id is
    optional — generated server-side when absent (the document-parse flow may
    already have minted one). financial_profile/authorizations/derived_flags/
    entities default empty, matching the contract's optional-with-defaults shape."""
    case_id: str | None = None
    patient: dict
    insurance: dict = Field(default_factory=dict)
    financial_profile: dict = Field(default_factory=dict)
    authorizations: dict = Field(default_factory=dict)
    bill: dict
    eob: dict
    derived_flags: list[dict] = Field(default_factory=list)
    entities: list[dict] = Field(default_factory=list)


@router.post("")
def create_case(body: CreateCaseRequest) -> dict:
    """Create a case from a JobSpec-shaped body: validates against the JobSpec
    contract mirror (models.JobSpec, itself a mirror of
    contracts/job_spec.schema.json), stores it in case_store (the source of
    truth every other endpoint in this build reads from), and best-effort
    upserts a Supabase cases row so calls.case_id FKs resolve later. Returns
    {"case_id": ...} — GET /cases/{case_id} reads it straight back."""
    case_id = str(body.case_id or uuidlib.uuid4())
    patient = body.patient or {}
    if not patient.get("legal_name") or not patient.get("dob"):
        raise HTTPException(422, "patient.legal_name and patient.dob are required "
                                 "(contracts/job_spec.schema.json)")

    spec_dict = {**body.model_dump(), "case_id": case_id}
    try:
        JobSpec.model_validate(spec_dict)
    except ValidationError as err:
        raise HTTPException(422, f"invalid job spec: {err.errors()}") from err

    case_store.put(case_id, "job_spec", spec_dict)
    db.ensure_case(case_id, spec_dict, None)  # best-effort; no-op offline
    return {"case_id": case_id}


@router.get("/demo", response_model=JobSpec)
def get_demo_case() -> dict:
    """Maya's fixture case — lets web + agents integrate before parsing exists.
    Served through spec_for_case so any captured financial answers (voice intake
    / manual card) overlay onto it — the /confirm screen reads this."""
    return spec_for_case("demo")


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
    return spec_for_case("demo")


@router.get("/{case_id}", response_model=JobSpec)
def get_case(case_id: str) -> dict:
    return _resolve_spec(case_id)


@router.get("/{case_id}/flags")
def get_case_flags(case_id: str) -> dict:
    """Red flags for the case. A scenario-loaded case's flags are the
    code-generated answer key (case_store "flags" slot) — already computed
    against the real lookup layer, so we serve those verbatim rather than
    recomputing against the 5-CPT demo fixture. Everything else keeps the
    existing live engine computation (PRD §7)."""
    spec = _resolve_spec(case_id)
    stored_flags = case_store.get(case_id, "flags")
    if stored_flags:
        return {"case_id": case_id, "flags": stored_flags}
    return {"case_id": case_id, "flags": [f.model_dump() for f in flags_for_spec(spec)]}


class FinancialProfileInput(BaseModel):
    """The financial answers the documents can't provide — from the voice
    interview or the manual card on /intake. All optional; only the answered
    fields are persisted (they overlay onto the fixture profile)."""
    lump_sum_available: float | None = Field(default=None, ge=0)
    monthly_max: float | None = Field(default=None, ge=0)
    household_income: float | None = Field(default=None, ge=0)
    household_size: int | None = Field(default=None, ge=1)


# monthly_max is the endpoint's contract name; the JobSpec/dossier read
# max_monthly_payment, so persist under that key to overlay correctly.
_FINANCIAL_KEY_MAP = {
    "lump_sum_available": "lump_sum_available",
    "monthly_max": "max_monthly_payment",
    "household_income": "household_income",
    "household_size": "household_size",
}


@router.post("/{case_id}/financial-profile")
def set_case_financial_profile(case_id: str, body: FinancialProfileInput) -> dict:
    """Land the interview's / manual card's financial answers on the case.

    Persists the answered fields to cases.financial_profile (migration 0006) and
    overlays them onto the served JobSpec (spec_for_case), so /confirm shows the
    captured number and the dossier floor derived from it (floor =
    lump_sum_available) changes accordingly. `floor` in the response is that live
    dossier floor — proof the number reached the engine."""
    spec = _resolve_spec(case_id)            # 404s unknown cases before we write
    real_id = spec["case_id"]

    fields = {_FINANCIAL_KEY_MAP[k]: v
              for k, v in body.model_dump(exclude_none=True).items()}
    if not fields:
        raise HTTPException(400, "no financial fields provided")

    persisted = db.upsert_case_financial_profile(real_id, fields)

    overlaid = spec_for_case(real_id)        # re-reads with the just-saved overlay
    profile = overlaid["financial_profile"]
    floor = None
    try:  # best-effort: the floor is nice-to-have, must never fail the save
        spec_model = JobSpec.model_validate(overlaid)
        dossier = build_dossier(spec_model, flags_for_spec(overlaid), demo_benchmarks(),
                                load_vertical(), entity=spec_model.entities[0])
        floor = dossier.floor
    except Exception:  # noqa: BLE001
        floor = profile.get("lump_sum_available")

    return {
        "case_id": case_id,
        "financial_profile": profile,
        "floor": floor,
        "persisted": persisted,
    }


@router.get("/{case_id}/action_plan")
def get_case_action_plan(case_id: str, no_llm: bool = False) -> dict:
    """The pre-dial Action Plan for the /confirm screen (PRD §11 screen 3).

    `input` is the code-computed payload (every number/date/statute from the
    engine + J's config/levers.json — PRD §7). `copy` is the user-facing text:
    warm `claude -p` prose when available and honest, deterministic fallback
    otherwise. Pass ?no_llm=true to force the fallback (used for fast demos/tests).
    """
    spec_dict = _resolve_spec(case_id)
    spec = JobSpec.model_validate(spec_dict)
    flags, benchmarks = flags_for_spec(spec_dict), demo_benchmarks()
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
    # Open items (parked topics + scheduled callbacks + resolved) — frozen contract
    # for the case-file UI: [{lever, detail, amount_at_stake, status, next_attempt_at,
    # reference_number, resolution_date}]. Empty list without a DB / no items.
    items = db.list_open_items_by_case(spec_dict["case_id"]) or []
    open_items = [
        {k: it.get(k) for k in ("lever", "detail", "amount_at_stake", "status",
                                "next_attempt_at", "reference_number", "resolution_date")}
        for it in items
    ]
    return {
        "case_id": case_id,
        "outcomes": ranked,
        "lines": build_lines(spec, flags, benchmarks, best_final),
        "recommendation": build_recommendation(ranked),
        "open_items": open_items,
        # The case's own identifiers, so the patient can read them aloud on a
        # call (surfaced as copyable reference chips in the case view header).
        "account_number": spec.bill.account_number,
        "claim_number": spec.eob.claim_number,
    }
