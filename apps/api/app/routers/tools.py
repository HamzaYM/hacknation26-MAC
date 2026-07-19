"""ElevenLabs SERVER TOOLS — hit by the negotiator agent MID-CALL.

These are the honesty boundary (PRD §8.5): get_benchmark and the dossier are
the ONLY sources of numbers the agent may speak. report_lever_result is the
state machine's steering wheel: the agent reports what happened, code answers
with the next move. Signatures FROZEN at H3 (PRD §12).
"""
from fastapi import APIRouter
from pydantic import BaseModel

from .. import db
from ..config import load_vertical
from ..engine.state_machine import LadderStateMachine
from ..fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC, demo_benchmarks, demo_dossier
from ..fixtures_users import flags_for_spec, spec_for_case
from ..models import Lever, StrategyDossier

router = APIRouter()

# In-memory, per-process (docstring in engine/state_machine.py: Supabase later).
state_machine = LadderStateMachine(load_vertical())

# PSTN calls placed outside /calls/launch (or before it existed) key the
# in-memory ladder state AND the call_events stream on this stable id. It must
# be a REAL uuid: db._is_uuid silently drops events for anything else, which
# is how real-call events used to vanish (old default: "live-call").
LIVE_CALL_ID = "00000000-0000-0000-0000-00000000ca11"


def _ensure_call_row(call_id: str | None) -> dict | None:
    """The calls row for a mid-call tool hit, created on demand (demo case)
    when a real uuid has no row yet — so call_events/outcomes FKs resolve for
    PSTN calls that were never launched through the API. None without a DB."""
    if not call_id or not db._is_uuid(call_id):
        return None
    row = db.get_call(call_id)
    if row is None and db.available():
        db.ensure_demo_case()
        db.insert_call(call_id, DEMO_CASE_ID, counterparty="agent", status="live")
        row = db.get_call(call_id)
    return row


def _dossier_for_call(row: dict | None) -> StrategyDossier:
    """The launched call's persisted dossier when present; demo fixture fallback."""
    if row and row.get("dossier_id"):
        stored = db.get_dossier(str(row["dossier_id"]))
        if stored:
            return StrategyDossier(
                case_id=str(stored["case_id"]),
                target_entity=stored["target_entity"],
                route=stored["route"],
                levers=[Lever(**l) for l in stored["levers"]],
                anchor=stored["anchor"],
                target=stored["target"],
                floor=stored["floor"],
                citations=stored.get("citations") or [],
            )
    return demo_dossier()


class LeverResult(BaseModel):
    call_id: str = LIVE_CALL_ID
    lever: str
    result: str  # accepted | rejected | partial | stonewalled | escalated | hangup
    offer_amount: float | None = None  # what the agent is about to offer/settle at
    quote: str | None = None           # counterparty's words (stonewall phrase detection)


class LogEvent(BaseModel):
    call_id: str = LIVE_CALL_ID
    type: str  # transcript | tool_call | state_change | quote | escalation
    payload: dict = {}


@router.post("/get_case_brief")
def get_case_brief(body: dict) -> dict:
    """Verbatim JobSpec facts for the call (challenge: spec reused verbatim),
    with derived_flags computed live by the engine. When the body carries a
    call_id, the launched call's stored case resolves the spec (fixture
    fallback: Maya's demo case)."""
    spec_dict = DEMO_JOB_SPEC
    call_id = (body or {}).get("call_id")
    if call_id:
        row = db.get_call(call_id)
        if row is not None:
            spec_dict = spec_for_case(str(row["case_id"])) or DEMO_JOB_SPEC
    spec = dict(spec_dict)
    spec["derived_flags"] = [f.model_dump() for f in flags_for_spec(spec_dict)]
    return {"job_spec": spec}


@router.post("/get_benchmark")
def get_benchmark(body: dict) -> dict:
    """The only citable price source. body: {"cpt": "71046"}"""
    cpt = str(body.get("cpt", ""))
    row = demo_benchmarks().get(cpt)
    if not row:
        return {"found": False, "say": "I don't have a benchmark for that code."}
    return {"found": True, "benchmark": row}


@router.post("/report_lever_result")
def report_lever_result(body: LeverResult) -> dict:
    """Agent reports lever outcome → code returns the next ladder move.

    Per-call state is created on first contact from the call's persisted
    dossier (real launches) or the demo dossier (fixtures)."""
    row = _ensure_call_row(body.call_id)
    state_machine.ensure_call(body.call_id, _dossier_for_call(row))
    resp = state_machine.advance(
        body.call_id, body.lever, body.result,
        offer_amount=body.offer_amount, quote=body.quote,
    )
    # Persist the move for the War Room (no-op without a DB / non-uuid call ids)
    db.insert_event(body.call_id, "state_change",
                    {"rung": resp["current_rung"], "rung_index": resp["rung_index"]})
    if resp.get("escalation") or resp.get("escalation_required"):
        db.insert_event(body.call_id, "escalation", {"reason": resp.get("notes", "")})
    return resp


@router.post("/log_quote")
def log_quote(body: LogEvent) -> dict:
    payload = dict(body.payload)
    if "amount" in payload:  # the War Room ticker needs a number
        try:
            payload["amount"] = float(payload["amount"])
        except (TypeError, ValueError):
            pass
    _ensure_call_row(body.call_id)
    db.insert_event(body.call_id, "quote", payload)
    return {"logged": True}


@router.post("/log_event")
def log_event(body: LogEvent) -> dict:
    _ensure_call_row(body.call_id)
    db.insert_event(body.call_id, body.type, body.payload)
    return {"logged": True}


@router.post("/end_call_summary")
def end_call_summary(body: dict) -> dict:
    """Agent's structured wrap-up before hang-up: ref #, rep name, agreed action.
    Stages the outcome row; final extraction still happens on the post-call webhook."""
    call_id = body.get("call_id")
    if call_id:
        _ensure_call_row(call_id)
        db.insert_event(call_id, "tool_call",
                        {"name": "end_call_summary",
                         "result": body.get("agreed_action") or body.get("outcome_type") or "received"})
        if body.get("outcome_type"):
            original, final = body.get("original_amount"), body.get("final_amount")
            reduction_pct = (  # computed by code, never the LLM (contract)
                round(100 * (1 - float(final) / float(original)), 1)
                if original and final is not None else None
            )
            db.insert_outcome({
                "call_id": call_id,
                "outcome_type": body["outcome_type"],
                "original_amount": original,
                "final_amount": final,
                "reduction_pct": reduction_pct,
                "winning_lever": body.get("winning_lever"),
                "reference_number": body.get("reference_number"),
                "rep_name": body.get("rep_name"),
                "next_action": body.get("agreed_action"),
            })
    return {"received": True}
