"""Caller-side callback scheduler (APScheduler, in-process).

Parked open items become scheduled callbacks (next_attempt_at = now + config
callback_delay_hours, nudged into a business window). An AsyncIOScheduler wired
into the FastAPI lifespan re-hydrates jobs from open_items(status='scheduled')
on startup and fires them when due:
  · ELEVENLABS_OUTBOUND_ENABLED truthy → place a real callback via the place-real
    path, carrying the case's open items in the brief.
  · flag off (default) → log + insert a `callback_due` event and leave the item
    scheduled, so the case view shows it without anything dialing.

NOT ElevenLabs batch-calling — the caller owns the schedule so it survives config
changes and stays visible in-product.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, time, timedelta

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import db, elevenlabs_calls

log = logging.getLogger("negotiator.scheduler")

# Business window: Tue–Thu, 9am–4pm local. Callbacks that land outside it get
# nudged to the next window's mid-morning — reps are calmer, hold queues shorter.
_BUSINESS_DAYS = {1, 2, 3}          # Mon=0 … Sun=6  → Tue, Wed, Thu
_WINDOW_OPEN = time(9, 0)
_WINDOW_CLOSE = time(16, 0)
_MID_MORNING = 10                   # hour for the nudge target

scheduler = AsyncIOScheduler(executors={"default": ThreadPoolExecutor(4)})


def clamp_to_business_window(dt: datetime) -> datetime:
    """Nudge dt into the next Tue–Thu 9am–4pm window when it lands outside one.
    Inside the window it's returned unchanged. Pure + deterministic (unit-tested)."""
    d = dt
    for _ in range(8):  # bounded — a week always contains a Tue–Thu slot
        in_day = d.weekday() in _BUSINESS_DAYS
        if in_day and _WINDOW_OPEN <= d.time() <= _WINDOW_CLOSE:
            return d
        if in_day and d.time() < _WINDOW_OPEN:
            # same day, before it opens → this morning's mid-morning slot
            d = d.replace(hour=_MID_MORNING, minute=0, second=0, microsecond=0)
            continue
        # after hours or a non-business day → next day, mid-morning
        d = (d + timedelta(days=1)).replace(hour=_MID_MORNING, minute=0, second=0, microsecond=0)
    return d


# ── lifespan hooks ────────────────────────────────────────────────────────
def start() -> None:
    if not scheduler.running:
        scheduler.start()
    rehydrate()


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


def _parse_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def rehydrate() -> int:
    """Re-schedule one job per case with scheduled open items still due — called on
    startup so callbacks survive restarts. Returns the number of jobs registered."""
    items = db.list_scheduled_open_items() or []
    earliest: dict[str, datetime] = {}
    for it in items:
        cid, when = it.get("case_id"), _parse_dt(it.get("next_attempt_at"))
        if cid and when and (cid not in earliest or when < earliest[cid]):
            earliest[cid] = when
    for cid, when in earliest.items():
        _schedule_case(cid, when)
    if earliest:
        log.info("scheduler re-hydrated %d callback job(s)", len(earliest))
    return len(earliest)


def schedule_callback(case_id: str, when: datetime) -> None:
    """Register/replace a case's callback job (called from end_call_summary)."""
    if scheduler.running:
        _schedule_case(case_id, when)


def _schedule_case(case_id: str, when: datetime) -> None:
    scheduler.add_job(run_callback, "date", run_date=when, args=[case_id],
                      id=f"callback:{case_id}", replace_existing=True, misfire_grace_time=3600)


# ── job body ──────────────────────────────────────────────────────────────
def run_callback(case_id: str) -> None:
    """Fire a due callback for a case: dial when the outbound flag is on, otherwise
    log + insert a `callback_due` event per item and leave everything scheduled."""
    items = db.list_open_items_by_case(case_id) or []
    scheduled = [it for it in items if it.get("status") == "scheduled"]
    if not scheduled:
        return
    if elevenlabs_calls.enabled():
        _dial_callback(case_id, scheduled)
    else:
        for it in scheduled:
            created = it.get("created_call_id")
            if created:
                db.insert_event(created, "callback_due",
                                {"lever": it.get("lever"), "detail": it.get("detail"),
                                 "next_attempt_at": it.get("next_attempt_at")})
        log.info("callback due for case %s — outbound flag off, %d item(s) left scheduled",
                 case_id, len(scheduled))


def callback_dynamic_variables(spec, dossier, scheduled: list[dict]) -> dict:
    """Per-call dynamic_variables for a scheduled callback: the usual case facts plus
    an open-items summary and the prior reference numbers (the re-raise brief, item 7)."""
    open_summary = "; ".join(
        (it.get("lever") or "item").replace("_", " ") + (f" ({it['detail']})" if it.get("detail") else "")
        for it in scheduled
    )
    prior_refs = ", ".join(sorted({it["reference_number"] for it in scheduled
                                   if it.get("reference_number")}))
    return {
        "patient_name": spec.patient.get("legal_name", ""),
        "account_number": spec.bill.account_number,
        "target_entity": f"{spec.entities[0].name} patient financial services",
        "route": dossier.route,
        "anchor": f"{dossier.anchor:.0f}",
        "target": f"{dossier.target:.0f}",
        "is_callback": "true",
        "open_items": open_summary,
        "prior_reference_numbers": prior_refs,
    }


# Callback dial target: real per-entity numbers are a follow-up; until then a
# callback dials the same demo line as /calls/place-real (env override wins).
_CALLBACK_NUMBER = os.environ.get("CALLBACK_TO_NUMBER", "+18576757033")


def _dial_callback(case_id: str, scheduled: list[dict]) -> None:
    from .config import load_vertical
    from .engine.dossier import build_dossier
    from .fixtures import demo_benchmarks
    from .fixtures_users import flags_for_spec, spec_for_case
    from .models import JobSpec

    spec_dict = spec_for_case(case_id)
    if spec_dict is None:
        log.warning("callback for unknown case %s — skipping dial", case_id)
        return
    spec = JobSpec.model_validate(spec_dict)
    entity = spec.entities[0]
    dossier = build_dossier(spec, flags_for_spec(spec_dict), demo_benchmarks(),
                            load_vertical(), entity=entity)
    call_id = str(uuid.uuid4())
    dossier_id = db.insert_dossier(case_id, dossier)
    db.insert_call(call_id, case_id, counterparty="agent", dossier_id=dossier_id)
    resp = elevenlabs_calls.outbound_call(
        os.environ.get("ELEVENLABS_AGENT_ID_NEGOTIATOR", ""),
        os.environ.get("ELEVENLABS_PHONE_NUMBER_ID", ""),
        _CALLBACK_NUMBER,
        conversation_initiation_client_data={
            "dynamic_variables": callback_dynamic_variables(spec, dossier, scheduled)
        },
    )
    conversation_id = resp.get("conversation_id")
    if conversation_id:
        db.set_call_conversation(call_id, conversation_id)
        db.update_call_status(call_id, "ringing")
    log.info("placed scheduled callback for case %s (call %s)", case_id, call_id)
