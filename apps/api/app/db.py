"""Supabase persistence — direct psycopg2 over SUPABASE_DB_URL (same approach
as scripts/provision_supabase.py; no extra deps).

Every helper is BEST-EFFORT: when the env/DB is unavailable (pytest, offline
dev) it logs a single warning and becomes a no-op returning None, so the API
keeps serving fixtures and the 27 contract tests stay green without a DB.
"""
from __future__ import annotations

import logging
import os
import threading
import urllib.parse
import uuid as uuidlib
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC

log = logging.getLogger("negotiator.db")

CALL_EVENT_TYPES = {"transcript", "tool_call", "state_change", "quote", "escalation"}

_lock = threading.RLock()
_conn: Any = None
_warned = False


def _connect():
    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not url:
        return None
    try:
        return psycopg2.connect(url, connect_timeout=10)
    except psycopg2.OperationalError:
        # retry with the password percent-encoded (provision_supabase.py pattern)
        parts = urllib.parse.urlsplit(url)
        if not parts.password:
            raise
        enc = urllib.parse.quote(parts.password, safe="")
        netloc = f"{parts.username}:{enc}@{parts.hostname}" + (f":{parts.port}" if parts.port else "")
        return psycopg2.connect(urllib.parse.urlunsplit(parts._replace(netloc=netloc)), connect_timeout=10)


def _get_conn():
    global _conn, _warned
    if _conn is not None and not _conn.closed:
        return _conn
    try:
        _conn = _connect()
        if _conn is not None:
            _conn.autocommit = True
        elif not _warned:
            log.warning("SUPABASE_DB_URL not set — persistence disabled (fixture-only mode)")
            _warned = True
    except Exception as err:  # noqa: BLE001 — any connect failure means "no DB"
        if not _warned:
            log.warning("Supabase unreachable — persistence disabled: %s", str(err).splitlines()[0])
            _warned = True
        _conn = None
    return _conn


def _run(sql: str, params: tuple | None = None, fetch: bool = False):
    """Execute best-effort. Returns rows (fetch=True), True, or None on failure."""
    global _conn
    with _lock:
        conn = _get_conn()
        if conn is None:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()] if fetch else True
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as err:
            log.warning("DB connection lost, dropping it: %s", str(err).splitlines()[0])
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
            _conn = None
            return None
        except psycopg2.Error as err:
            log.warning("DB statement skipped: %s", str(err).splitlines()[0])
            return None


def available() -> bool:
    with _lock:
        return _get_conn() is not None


def _is_uuid(value: str | None) -> bool:
    try:
        uuidlib.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _jsonable(row: dict) -> dict:
    out: dict = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif isinstance(v, uuidlib.UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out


# ── cases ─────────────────────────────────────────────────────────────────
def ensure_case(case_id: str, spec: dict, owner_email: str | None = None):
    """Upsert a fixture case row so calls.case_id FK resolves (0002: owner_email)."""
    return _run(
        """
        insert into cases (id, patient, insurance, financial_profile, authorizations, status, owner_email)
        values (%s, %s, %s, %s, %s, 'intake', %s)
        on conflict (id) do update set owner_email = coalesce(excluded.owner_email, cases.owner_email)
        """,
        (case_id, Json(spec["patient"]), Json(spec["insurance"]),
         Json(spec["financial_profile"]), Json(spec["authorizations"]), owner_email),
    )


def ensure_demo_case():
    """Upsert the fixture case row so calls.case_id FK resolves."""
    return ensure_case(DEMO_CASE_ID, DEMO_JOB_SPEC)


def get_case_by_owner_email(email: str) -> dict | None:
    rows = _run("select * from cases where owner_email = %s order by created_at limit 1",
                (email,), fetch=True)
    return _jsonable(rows[0]) if rows else None


def set_case_status(case_id: str, status: str):
    if not _is_uuid(case_id):
        return None
    return _run("update cases set status = %s where id = %s", (status, case_id))


# ── voice preference (per case) ───────────────────────────────────────────
def get_case_voice(case_id: str) -> str | None:
    """The chosen voice_id for a case, or None (no row / no DB / table absent)."""
    if not _is_uuid(case_id):
        return None
    rows = _run("select voice_id from case_voice_prefs where case_id = %s", (case_id,), fetch=True)
    return rows[0]["voice_id"] if rows else None


def set_case_voice(case_id: str, voice_id: str, voice_label: str | None = None) -> bool:
    """Upsert the chosen voice. Returns True only when it actually persisted."""
    if not _is_uuid(case_id):
        return False
    result = _run(
        """
        insert into case_voice_prefs (case_id, voice_id, voice_label, updated_at)
        values (%s, %s, %s, now())
        on conflict (case_id) do update
          set voice_id = excluded.voice_id,
              voice_label = excluded.voice_label,
              updated_at = now()
        """,
        (case_id, voice_id, voice_label),
    )
    return result is True


# ── documents ─────────────────────────────────────────────────────────────
def insert_document(document_id: str, case_id: str, kind: str, storage_path: str, parsed: dict):
    if not _is_uuid(document_id) or not _is_uuid(case_id):
        return None
    return _run(
        """
        insert into documents (id, case_id, kind, storage_path, parsed, parse_status)
        values (%s, %s, %s, %s, %s, 'parsed')
        on conflict (id) do nothing
        """,
        (document_id, case_id, kind, storage_path, Json(parsed)),
    )


# ── strategy dossiers ─────────────────────────────────────────────────────
def insert_dossier(case_id: str, dossier) -> str | None:
    """Persist a StrategyDossier; returns the new row id (report joins on it)."""
    rows = _run(
        """
        insert into strategy_dossiers (case_id, target_entity, route, levers, anchor, target, floor, citations)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (case_id, dossier.target_entity, dossier.route,
         Json([l.model_dump() for l in dossier.levers]),
         dossier.anchor, dossier.target, dossier.floor, Json(dossier.citations)),
        fetch=True,
    )
    return str(rows[0]["id"]) if rows else None


def get_dossier(dossier_id: str) -> dict | None:
    if not _is_uuid(dossier_id):
        return None
    rows = _run("select * from strategy_dossiers where id = %s", (dossier_id,), fetch=True)
    return _jsonable(rows[0]) if rows else None


# ── calls ─────────────────────────────────────────────────────────────────
def insert_call(call_id: str, case_id: str, counterparty: str = "agent",
                status: str = "queued", dossier_id: str | None = None):
    return _run(
        """
        insert into calls (id, case_id, counterparty, status, dossier_id)
        values (%s, %s, %s, %s, %s)
        on conflict (id) do nothing
        """,
        (call_id, case_id, counterparty, status, dossier_id),
    )


def update_call_status(call_id: str, status: str):
    if not _is_uuid(call_id):
        return None
    return _run(
        """
        update calls set status = %s,
          started_at = case when %s = 'live' and started_at is null then now() else started_at end,
          ended_at   = case when %s in ('ended','failed') and ended_at is null then now() else ended_at end
        where id = %s
        """,
        (status, status, status, call_id),
    )


def get_call(call_id: str) -> dict | None:
    if not _is_uuid(call_id):
        return None
    rows = _run("select * from calls where id = %s", (call_id,), fetch=True)
    return _jsonable(rows[0]) if rows else None


def get_call_by_conversation(conversation_id: str) -> dict | None:
    rows = _run("select * from calls where elevenlabs_conversation_id = %s",
                (conversation_id,), fetch=True)
    return _jsonable(rows[0]) if rows else None


def get_active_real_call() -> dict | None:
    """The most recent ringing/live call linked to an ElevenLabs conversation —
    where tool hits that arrive without our call_id attach (ElevenLabs webhook
    tools don't know internal ids; see tools._resolve_call_id)."""
    rows = _run("select * from calls where elevenlabs_conversation_id is not null "
                "and status in ('ringing', 'live') order by started_at desc nulls last limit 1",
                fetch=True)
    return _jsonable(rows[0]) if rows else None


def set_call_conversation(call_id: str, conversation_id: str):
    """Link a dialed call to its ElevenLabs conversation so the post-call
    webhook (matched by conversation_id) lands transcript + audio on the row."""
    if not _is_uuid(call_id):
        return None
    return _run("update calls set elevenlabs_conversation_id = %s where id = %s",
                (conversation_id, call_id))


def set_call_recording(call_id: str, recording_path: str):
    if not _is_uuid(call_id):
        return None
    return _run("update calls set recording_path = %s where id = %s", (recording_path, call_id))


# ── call events (the War Room's Realtime stream) ──────────────────────────
def insert_event(call_id: str, type_: str, payload: dict) -> int | None:
    if not _is_uuid(call_id) or type_ not in CALL_EVENT_TYPES:
        return None
    rows = _run(
        "insert into call_events (call_id, type, payload) values (%s, %s, %s) returning id",
        (call_id, type_, Json(payload)),
        fetch=True,
    )
    return int(rows[0]["id"]) if rows else None


def get_events_by_ids(event_ids: list[int]) -> list[dict] | None:
    """The call_events referenced by an outcome's evidence_event_ids, id-ordered."""
    ids = [int(i) for i in (event_ids or [])]
    if not ids:
        return []
    rows = _run(
        "select id, ts, type, payload from call_events where id = any(%s) order by id",
        (ids,),
        fetch=True,
    )
    return [_jsonable(r) for r in rows] if rows is not None else None


# ── outcomes ──────────────────────────────────────────────────────────────
def insert_outcome(outcome: dict):
    """Insert a CallOutcome (only the fields that exist in the outcomes table)."""
    if not _is_uuid(outcome.get("call_id")):
        return None
    return _run(
        """
        insert into outcomes (call_id, outcome_type, original_amount, final_amount, reduction_pct,
                              winning_lever, reference_number, rep_name, next_action,
                              evidence_event_ids, honesty_audit)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (outcome["call_id"], outcome["outcome_type"], outcome.get("original_amount"),
         outcome.get("final_amount"), outcome.get("reduction_pct"), outcome.get("winning_lever"),
         outcome.get("reference_number"), outcome.get("rep_name"), outcome.get("next_action"),
         outcome.get("evidence_event_ids") or [],
         Json(outcome["honesty_audit"]) if outcome.get("honesty_audit") is not None else None),
    )


def get_case_outcomes(case_id: str) -> list[dict] | None:
    if not _is_uuid(case_id):
        return None
    rows = _run(
        """
        select o.*, d.target_entity, d.route, c.recording_path, c.ended_at
        from outcomes o
        join calls c on c.id = o.call_id
        left join strategy_dossiers d on d.id = c.dossier_id
        where c.case_id = %s
        """,
        (case_id,),
        fetch=True,
    )
    return [_jsonable(r) for r in rows] if rows is not None else None
