"""ElevenLabs SERVER TOOLS — hit by the negotiator agent MID-CALL.

These are the honesty boundary (PRD §8.5): get_benchmark and the dossier are
the ONLY sources of numbers the agent may speak. report_lever_result is the
state machine's steering wheel: the agent reports what happened, code answers
with the next move. Signatures FROZEN at H3 (PRD §12).
"""
import re
from datetime import date, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel

from .. import db, scheduler
from ..config import load_vertical
from ..engine.dossier import compute_501r_window
from ..engine.state_machine import LadderStateMachine
from ..fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC, demo_benchmarks, demo_dossier
from ..fixtures_users import flags_for_spec, spec_for_case
from ..models import Lever, StrategyDossier
from ..scheduler import clamp_to_business_window

router = APIRouter()

# In-memory, per-process (docstring in engine/state_machine.py: Supabase later).
state_machine = LadderStateMachine(load_vertical())

# PSTN calls placed outside /calls/launch (or before it existed) key the
# in-memory ladder state AND the call_events stream on this stable id. It must
# be a REAL uuid: db._is_uuid silently drops events for anything else, which
# is how real-call events used to vanish (old default: "live-call").
LIVE_CALL_ID = "00000000-0000-0000-0000-00000000ca11"

# Outcomes that represent a concrete agreed win — banked only with a reference
# number, rep name, and agreed action (A4). documented_decline/callback/charity
# stay ungated: a hangup or a follow-up can't be pushed back. ("settlement" is
# carried per spec though the current outcomes enum uses reduction/payment_plan.)
GATED_OUTCOMES = {"reduction", "payment_plan", "settlement"}


def _append_note(base: str | None, note: str) -> str:
    return f"{base}; {note}" if base else note


def _looks_like_bare_name(value: object) -> bool:
    """A reference_number that's really a rep's first name leaked into the wrong
    field ("Bob"): a single short word, all letters, no digits. Real confirmation
    numbers always carry a digit (and usually a prefix/dash)."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    return bool(v) and v.isalpha() and len(v) <= 15


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


def _resolve_call_id(call_id: str | None) -> str:
    """ElevenLabs webhook tools don't know our internal call ids, so tool hits
    from real PSTN calls arrive with the LIVE_CALL_ID default. When a real call
    is ringing/live (conversation id set), attach them to it instead — and flip
    ringing → live on first contact so the War Room picks it up immediately."""
    if call_id and call_id != LIVE_CALL_ID:
        return call_id
    row = db.get_active_real_call() if db.available() else None
    if row:
        resolved = str(row["id"])
        if row.get("status") == "ringing":
            db.update_call_status(resolved, "live")
        return resolved
    return LIVE_CALL_ID


def _dossier_for_call(row: dict | None) -> StrategyDossier:
    """The launched call's persisted dossier when present; demo fixture fallback."""
    if row and row.get("dossier_id"):
        stored = db.get_dossier(str(row["dossier_id"]))
        if stored:
            # The 501(r) clock isn't persisted on strategy_dossiers (additive fields);
            # recompute it from the case's bill so the window survives the DB round-trip.
            spec_dict = spec_for_case(str(stored["case_id"])) or DEMO_JOB_SPEC
            bill = spec_dict.get("bill", {}) or {}
            days_since, inside_window = compute_501r_window(
                bill.get("statement_date"), bool(bill.get("nonprofit_status")))
            return StrategyDossier(
                case_id=str(stored["case_id"]),
                target_entity=stored["target_entity"],
                route=stored["route"],
                levers=[Lever(**l) for l in stored["levers"]],
                anchor=stored["anchor"],
                target=stored["target"],
                floor=stored["floor"],
                citations=stored.get("citations") or [],
                days_since_first_statement=days_since,
                inside_501r_window=inside_window,
            )
    return demo_dossier()


class LeverResult(BaseModel):
    call_id: str = LIVE_CALL_ID
    lever: str
    result: str  # accepted | rejected | partial | stonewalled | escalated | hangup
    offer_amount: float | None = None  # what the agent is about to offer/settle at
    quote: str | None = None           # counterparty's words (stonewall phrase detection)
    questions_asked: list[str] = []    # coverage tags the agent covered this exchange


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
    call_id = _resolve_call_id((body or {}).get("call_id"))
    if call_id:
        row = db.get_call(call_id)
        if row is not None:
            spec_dict = spec_for_case(str(row["case_id"])) or DEMO_JOB_SPEC
    spec = dict(spec_dict)
    spec["derived_flags"] = [f.model_dump() for f in flags_for_spec(spec_dict)]
    bill = spec_dict.get("bill", {}) or {}
    days_since, inside_window = compute_501r_window(
        bill.get("statement_date"), bool(bill.get("nonprofit_status")))
    return {
        "job_spec": spec,
        "days_since_first_statement": days_since,
        "inside_501r_window": inside_window,
    }


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
    call_id = _resolve_call_id(body.call_id)
    row = _ensure_call_row(call_id)
    state_machine.ensure_call(call_id, _dossier_for_call(row))
    resp = state_machine.advance(
        call_id, body.lever, body.result,
        offer_amount=body.offer_amount, quote=body.quote,
        questions_asked=body.questions_asked,
    )
    # Persist the move for the War Room (no-op without a DB / non-uuid call ids)
    db.insert_event(call_id, "state_change",
                    {"rung": resp["current_rung"], "rung_index": resp["rung_index"]})
    if resp.get("escalation") or resp.get("escalation_required"):
        db.insert_event(call_id, "escalation", {"reason": resp.get("notes", "")})
    # Coverage gap: the agent walked off a required-questions rung still missing
    # tags on the second pass — surface it to the War Room (A1).
    if resp.get("coverage_incomplete"):
        db.insert_event(call_id, "coverage_gap",
                        {"rung": resp["current_rung"], "missing": resp["coverage_incomplete"]})
    # Topic parked: an impasse set aside as an open item (escalation last resort).
    if resp.get("parked"):
        db.insert_event(call_id, "topic_parked", resp["parked"])
    return resp


@router.post("/log_quote")
def log_quote(body: LogEvent) -> dict:
    payload = dict(body.payload)
    if "amount" in payload:  # the War Room ticker needs a number
        try:
            payload["amount"] = float(payload["amount"])
        except (TypeError, ValueError):
            pass
    call_id = _resolve_call_id(body.call_id)
    _ensure_call_row(call_id)
    db.insert_event(call_id, "quote", payload)
    return {"logged": True}


@router.post("/log_event")
def log_event(body: LogEvent) -> dict:
    call_id = _resolve_call_id(body.call_id)
    _ensure_call_row(call_id)
    db.insert_event(call_id, body.type, body.payload)
    return {"logged": True}


def _resolution_date(agreed_action: str | None) -> date:
    """Best-effort resolution date from the agreed-action text; today when none parses."""
    if agreed_action:
        m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", agreed_action)
        if m:
            try:
                return date(int(m[1]), int(m[2]), int(m[3]))
            except ValueError:
                pass
        m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", agreed_action)
        if m:
            year = int(m[3])
            year += 2000 if year < 100 else 0
            try:
                return date(year, int(m[1]), int(m[2]))
            except ValueError:
                pass
    return date.today()


def _persist_open_items(call_id: str, case_id: str, body: dict, resolved_ok: bool = True) -> int:
    """End-of-call bookkeeping: unresolved parked topics → scheduled open_items (a
    callback is armed), and the winning lever → a resolved open_item with a
    resolution_date (2a). resolved_ok is False when the win was downgraded to a
    callback (A5, written confirmation pending) so nothing is marked resolved yet.
    Returns how many callbacks were scheduled."""
    parked = state_machine.parked_topics(call_id)
    winning = body.get("winning_lever")
    if winning and resolved_ok:
        db.insert_open_item(
            case_id, lever=winning, detail=body.get("agreed_action"),
            status="resolved", resolved_call_id=call_id,
            resolution_date=_resolution_date(body.get("agreed_action")),
            reference_number=body.get("reference_number"),
        )
    delay = load_vertical().get("callback_delay_hours", 5)
    next_attempt = clamp_to_business_window(datetime.now() + timedelta(hours=delay))
    scheduled = 0
    for p in parked:
        if winning and resolved_ok and p["lever"] == winning:
            continue  # resolved on this call — not left open
        db.insert_open_item(case_id, lever=p["lever"], detail=p.get("reason"),
                            status="scheduled", created_call_id=call_id,
                            next_attempt_at=next_attempt)
        scheduled += 1
    if scheduled:
        scheduler.schedule_callback(case_id, next_attempt)
    return scheduled


@router.post("/end_call_summary")
def end_call_summary(body: dict) -> dict:
    """Agent's structured wrap-up before hang-up: ref #, rep name, agreed action.
    Stages the outcome row; final extraction still happens on the post-call webhook.

    Soft-fail gates (never hard-block a hangup):
      A4 — a gated win missing reference_number/rep_name/agreed_action is pushed
           back once; a second attempt with confirm_incomplete:true is banked + flagged.
      A5 — a monetary settlement (final_amount set) without written_confirmation:true
           is downgraded to a callback to secure the letter first (kept + marked with
           confirm_incomplete:true).
      A6 — a reference_number with no read_back event on the call is flagged
           reference_number_unverified (warning, not a block).
    """
    call_id = _resolve_call_id(body.get("call_id"))
    call_row = _ensure_call_row(call_id)
    db.insert_event(call_id, "tool_call",
                    {"name": "end_call_summary",
                     "result": body.get("agreed_action") or body.get("outcome_type") or "received"})

    outcome_type = body.get("outcome_type")
    if not outcome_type:
        return {"received": True}

    confirm_incomplete = bool(body.get("confirm_incomplete"))

    # Reference-field guard: a bare first name in reference_number ("Bob") is a
    # rep name that leaked into the wrong field, never a real confirmation
    # number. Reroute it to rep_name when that's empty, otherwise drop it. Runs
    # before the A4 gate and the outcome insert so the name can't be banked as a
    # reference or satisfy the gated-win check.
    ref_moved_to_rep = ref_dropped = False
    if _looks_like_bare_name(body.get("reference_number")):
        if not body.get("rep_name"):
            body["rep_name"] = body["reference_number"].strip()
            ref_moved_to_rep = True
        else:
            ref_dropped = True
        body["reference_number"] = None

    # A4: gated wins need the paper trail before we bank them.
    missing = [f for f in ("reference_number", "rep_name", "agreed_action")
               if outcome_type in GATED_OUTCOMES and not body.get(f)]
    if missing and not confirm_incomplete:
        return {"received": False, "missing": missing,
                "say": "get the missing items before hanging up"}

    # A5: money without written confirmation isn't a real win yet.
    final = body.get("final_amount")
    next_action = body.get("agreed_action")
    written_confirmation_pending = False
    downgraded = False
    if final is not None and not body.get("written_confirmation"):
        if confirm_incomplete:
            written_confirmation_pending = True
            next_action = _append_note(
                next_action, "written confirmation still pending — get it in writing first")
        else:
            outcome_type = "callback"
            downgraded = True
            next_action = ("secure written confirmation (zero balance, paid in full, "
                           "no collections referral) before money moves")

    if missing:  # accepted-incomplete (A4): record what was still missing
        next_action = _append_note(next_action, f"missing at hangup: {', '.join(missing)}")

    original = body.get("original_amount")
    reduction_pct = (  # computed by code, never the LLM (contract)
        round(100 * (1 - float(final) / float(original)), 1)
        if original and final is not None else None
    )
    db.insert_outcome({
        "call_id": call_id,
        "outcome_type": outcome_type,
        "original_amount": original,
        "final_amount": final,
        "reduction_pct": reduction_pct,
        "winning_lever": body.get("winning_lever"),
        "reference_number": body.get("reference_number"),
        "rep_name": body.get("rep_name"),
        "next_action": next_action,
    })

    resp: dict = {"received": True}
    if missing:
        resp["missing_fields"] = missing
    if written_confirmation_pending:
        resp["written_confirmation_pending"] = True
    if downgraded:
        resp["outcome_downgraded"] = "callback"
    # A6: a reference number nobody read back is unverified — flag, don't block.
    if body.get("reference_number") and not db.has_event(call_id, "read_back"):
        resp.setdefault("warnings", []).append("reference_number_unverified")
    if ref_moved_to_rep:
        resp.setdefault("warnings", []).append("reference_number_looked_like_name_moved_to_rep_name")
    if ref_dropped:
        resp.setdefault("warnings", []).append("reference_number_looked_like_name_dropped")

    # Parked topics persist as scheduled callbacks; the winning lever resolves
    # (unless the win was downgraded to a callback for a pending written confirmation).
    case_id = str(call_row["case_id"]) if call_row else None
    if case_id:
        _persist_open_items(call_id, case_id, body, resolved_ok=not downgraded)
    # Close ritual: the summary is banked → the agent should hang up now, not wait
    # for the rep (every extra second on the line is billed per-minute).
    resp["end_call_now"] = True
    return resp
