"""Call-behavior fixes (PART 2): park → open items, self-scheduled callbacks with a
business-window clamp + flag-off behavior, and the end_call_now hang-up signal."""
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import db, scheduler
from app.fixtures import DEMO_CASE_ID
from app.main import app
from app.routers import tools
from app.routers.tools import LeverResult
from app.scheduler import clamp_to_business_window


@pytest.fixture
def client():
    return TestClient(app)


# ── migration / event types ───────────────────────────────────────────────
def test_new_call_event_types_registered():
    assert {"topic_parked", "callback_due"} <= db.CALL_EVENT_TYPES


# ── scheduler: business-window clamp (Tue–Thu, 9am–4pm) ───────────────────
def test_clamp_leaves_a_wed_midmorning_untouched():
    dt = datetime(2026, 7, 15, 11, 0)  # Wednesday, inside the window
    assert clamp_to_business_window(dt) == dt


def test_clamp_pushes_saturday_into_next_business_window():
    dt = datetime(2026, 7, 18, 14, 0)  # Saturday
    out = clamp_to_business_window(dt)
    assert out.weekday() in {1, 2, 3}          # Tue–Thu
    assert 9 <= out.hour <= 16
    assert out > dt


def test_clamp_pushes_after_hours_to_next_day_midmorning():
    dt = datetime(2026, 7, 14, 20, 0)  # Tuesday 8pm (after close)
    out = clamp_to_business_window(dt)
    assert out.date() > dt.date()
    assert out.hour == 10
    assert out.weekday() in {1, 2, 3}


def test_clamp_pushes_before_hours_to_same_day_midmorning():
    dt = datetime(2026, 7, 15, 6, 0)  # Wednesday 6am (before open)
    out = clamp_to_business_window(dt)
    assert out.date() == dt.date()
    assert out.hour == 10


# ── scheduler: flag-off callback fires no dial, just a callback_due event ──
def test_run_callback_flag_off_logs_callback_due_and_does_not_dial(monkeypatch):
    events, dialed = [], []
    created_call = "00000000-0000-0000-0000-0000000000aa"
    monkeypatch.setattr(scheduler.db, "list_open_items_by_case", lambda cid: [
        {"status": "scheduled", "lever": "line_item_disputes", "detail": "stonewalled twice",
         "created_call_id": created_call, "next_attempt_at": "2026-07-21T10:00:00"},
    ])
    monkeypatch.setattr(scheduler.db, "insert_event",
                        lambda cid, type_, payload: events.append((cid, type_, payload)))
    monkeypatch.setattr(scheduler.elevenlabs_calls, "enabled", lambda: False)
    monkeypatch.setattr(scheduler, "_dial_callback", lambda *a, **k: dialed.append(a))

    scheduler.run_callback("some-case")

    assert dialed == []                       # nothing dialed while the flag is off
    assert len(events) == 1
    cid, type_, payload = events[0]
    assert type_ == "callback_due"
    assert cid == created_call
    assert payload["lever"] == "line_item_disputes"


def test_run_callback_flag_on_dials(monkeypatch):
    dialed = []
    monkeypatch.setattr(scheduler.db, "list_open_items_by_case", lambda cid: [
        {"status": "scheduled", "lever": "benchmark_anchor", "created_call_id": None},
    ])
    monkeypatch.setattr(scheduler.elevenlabs_calls, "enabled", lambda: True)
    monkeypatch.setattr(scheduler, "_dial_callback", lambda case_id, items: dialed.append(case_id))

    scheduler.run_callback("case-99")

    assert dialed == ["case-99"]


# ── open-items lifecycle: park → end_call_summary → scheduled row + end_call_now ──
def test_park_then_summary_persists_open_items_and_signals_hangup(monkeypatch):
    call_id = str(uuid.uuid4())
    open_items, events = [], []

    # Give the tool a resolvable call row (case_id) without a real DB.
    monkeypatch.setattr(tools.db, "get_call", lambda cid: {"case_id": DEMO_CASE_ID})
    monkeypatch.setattr(tools.db, "insert_event",
                        lambda cid, type_, payload: events.append((type_, payload)))
    monkeypatch.setattr(tools.db, "insert_outcome", lambda outcome: None)
    monkeypatch.setattr(tools.db, "has_event", lambda cid, type_: True)  # ref read back

    def _rec_open_item(case_id, lever, **kw):
        open_items.append({"case_id": case_id, "lever": lever, **kw})
    monkeypatch.setattr(tools.db, "insert_open_item", _rec_open_item)

    # Park line_item_disputes: two unhedged stonewalls on the same lever.
    for _ in range(2):
        tools.report_lever_result(LeverResult(
            call_id=call_id, lever="line_item_disputes", result="stonewalled"))

    assert any(t == "topic_parked" for t, _ in events)

    # Close the call with a win on a different lever.
    resp = tools.end_call_summary({
        "call_id": call_id,
        "outcome_type": "reduction",
        "final_amount": 1650.0,
        "original_amount": 4287.0,
        "reference_number": "REF-1",
        "rep_name": "Dana",
        "agreed_action": "adjustment posted by 2026-08-01",
        "winning_lever": "benchmark_anchor",
        "written_confirmation": True,
    })

    # The agent is told to hang up itself.
    assert resp["received"] is True
    assert resp["end_call_now"] is True

    # Parked topic → a scheduled open item with a next_attempt_at.
    scheduled = [i for i in open_items if i.get("status") == "scheduled"]
    assert len(scheduled) == 1
    assert scheduled[0]["lever"] == "line_item_disputes"
    assert scheduled[0]["next_attempt_at"] is not None

    # Winning lever → a resolved open item with a resolution_date parsed from the action.
    resolved = [i for i in open_items if i.get("status") == "resolved"]
    assert len(resolved) == 1
    assert resolved[0]["lever"] == "benchmark_anchor"
    assert str(resolved[0]["resolution_date"]) == "2026-08-01"


def test_end_call_summary_pushback_has_no_hangup_signal(monkeypatch):
    """A gated win missing its paper trail is pushed back (received:false) — the agent
    must NOT hang up yet, so end_call_now must be absent."""
    call_id = str(uuid.uuid4())
    monkeypatch.setattr(tools.db, "get_call", lambda cid: {"case_id": DEMO_CASE_ID})
    resp = tools.end_call_summary({"call_id": call_id, "outcome_type": "reduction"})
    assert resp["received"] is False
    assert "end_call_now" not in resp


# ── report endpoint exposes the open_items contract ───────────────────────
def test_report_exposes_open_items_contract(client, monkeypatch):
    monkeypatch.setattr(db, "list_open_items_by_case", lambda cid: [
        {"id": "x", "case_id": cid, "lever": "line_item_disputes",
         "detail": "stonewalled twice", "amount_at_stake": 412.0, "status": "scheduled",
         "created_call_id": "c", "resolved_call_id": None, "resolution_date": None,
         "next_attempt_at": "2026-07-21T10:00:00", "reference_number": None,
         "created_at": "2026-07-18T00:00:00"},
    ])
    resp = client.get(f"/cases/{DEMO_CASE_ID}/report")
    assert resp.status_code == 200
    items = resp.json()["open_items"]
    assert len(items) == 1
    assert set(items[0]) == {"lever", "detail", "amount_at_stake", "status",
                             "next_attempt_at", "reference_number", "resolution_date"}
    assert items[0]["status"] == "scheduled"
    assert items[0]["next_attempt_at"] == "2026-07-21T10:00:00"
