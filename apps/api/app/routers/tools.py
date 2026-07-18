"""ElevenLabs SERVER TOOLS — hit by the negotiator agent MID-CALL.

These are the honesty boundary (PRD §8.5): get_benchmark and the dossier are
the ONLY sources of numbers the agent may speak. report_lever_result is the
state machine's steering wheel: the agent reports what happened, code answers
with the next move. Signatures FROZEN at H3 (PRD §12).
"""
from fastapi import APIRouter
from pydantic import BaseModel

from ..config import load_vertical
from ..engine.state_machine import LadderStateMachine
from ..fixtures import DEMO_JOB_SPEC, demo_benchmarks, demo_dossier, demo_flags

router = APIRouter()

# In-memory, per-process (docstring in engine/state_machine.py: Supabase later).
state_machine = LadderStateMachine(load_vertical())


class LeverResult(BaseModel):
    call_id: str
    lever: str
    result: str  # accepted | rejected | partial | stonewalled | escalated | hangup
    offer_amount: float | None = None  # what the agent is about to offer/settle at
    quote: str | None = None           # counterparty's words (stonewall phrase detection)


class LogEvent(BaseModel):
    call_id: str
    type: str  # transcript | tool_call | state_change | quote | escalation
    payload: dict = {}


@router.post("/get_case_brief")
def get_case_brief(body: dict) -> dict:
    """Verbatim JobSpec facts for the call (challenge: spec reused verbatim),
    with derived_flags computed live by the engine."""
    spec = dict(DEMO_JOB_SPEC)
    spec["derived_flags"] = [f.model_dump() for f in demo_flags()]
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

    Per-call state is created on first contact from the demo dossier
    (fixtures) until real per-case dossiers are persisted.
    """
    state_machine.ensure_call(body.call_id, demo_dossier())
    return state_machine.advance(
        body.call_id, body.lever, body.result,
        offer_amount=body.offer_amount, quote=body.quote,
    )


@router.post("/log_quote")
def log_quote(body: LogEvent) -> dict:
    # TODO(Hamza): insert call_events row (type=quote) → Supabase Realtime → War Room
    return {"logged": True}


@router.post("/log_event")
def log_event(body: LogEvent) -> dict:
    # TODO(Hamza): insert call_events row → Realtime
    return {"logged": True}


@router.post("/end_call_summary")
def end_call_summary(body: dict) -> dict:
    """Agent's structured wrap-up before hang-up: ref #, rep name, agreed action."""
    # TODO(Hamza): stage partial CallOutcome; final extraction happens on the post-call webhook
    return {"received": True}
