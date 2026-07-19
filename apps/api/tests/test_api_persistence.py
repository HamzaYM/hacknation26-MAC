"""Endpoint contracts with the DB monkeypatched OFF — launch/confirm/report
must keep working in fixture-only mode (offline dev, CI, TestClient)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(db, "_get_conn", lambda: None)  # force no-op persistence
    return TestClient(app)


def test_launch_returns_real_uuids(client):
    resp = client.post("/calls/launch", json={"case_id": "demo", "simulate": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == "demo"
    assert [l["entity"] for l in body["launched"]] == [
        "Mercy General Hospital", "Bay State Emergency Physicians", "Meridian Recovery Services"]
    for launched in body["launched"]:
        uuid.UUID(launched["call_id"])  # real uuid, not stub-call-N
        assert launched["status"] == "queued"


def test_launch_unknown_case_404(client):
    assert client.post("/calls/launch", json={"case_id": "nope"}).status_code == 404


def test_get_call_404_when_missing(client):
    assert client.get(f"/calls/{uuid.uuid4()}").status_code == 404


def test_confirm_persists_and_keeps_shape(client):
    assert client.post("/cases/demo/confirm").json() == {"case_id": "demo", "status": "confirmed"}
    assert client.post("/cases/nope/confirm").status_code == 404


def test_report_serves_fixture_lines_without_outcomes(client):
    resp = client.get("/cases/demo/report")
    assert resp.status_code == 200
    report = resp.json()
    assert report["outcomes"] == []
    assert {l["cpt"] for l in report["lines"]} == {"99283", "71046", "80053", "85025", "96374"}
    assert report["recommendation"].startswith("No completed calls")
    assert client.get("/cases/nope/report").status_code == 404


def test_report_outcomes_carry_entity_evidence_and_recording(client, monkeypatch):
    """Frozen contract: each outcome gains entity, evidence (its call_events,
    ordered), and recording_url (signed) when recording_path exists."""
    from app.routers import cases

    events = {
        7: {"id": 7, "ts": "2026-07-18T00:00:07", "type": "quote", "payload": {"amount": 1650.0}},
        9: {"id": 9, "ts": "2026-07-18T00:00:09", "type": "transcript",
            "payload": {"speaker": "rep", "text": "approved"}},
    }
    monkeypatch.setattr(cases.db, "get_case_outcomes", lambda case_id: [
        {"outcome_type": "reduction", "original_amount": 4287.0, "final_amount": 1650.0,
         "target_entity": "Mercy General Hospital", "evidence_event_ids": [9, 7],
         "recording_path": "recordings/call-1.mp3"},
        {"outcome_type": "callback", "final_amount": None, "target_entity": None,
         "evidence_event_ids": [], "recording_path": None},
    ])
    monkeypatch.setattr(cases.db, "get_events_by_ids",
                        lambda ids: [events[i] for i in sorted(ids)])
    monkeypatch.setattr(cases.storage, "sign_url",
                        lambda path: f"https://signed.example/{path}")

    outcomes = client.get("/cases/demo/report").json()["outcomes"]
    assert len(outcomes) == 2
    reduction, callback = outcomes
    assert reduction["entity"] == "Mercy General Hospital"
    assert [e["type"] for e in reduction["evidence"]] == ["quote", "transcript"]  # id-ordered
    assert set(reduction["evidence"][0]) == {"ts", "type", "payload"}
    assert reduction["recording_url"] == "https://signed.example/recordings/call-1.mp3"
    assert "recording_path" not in reduction
    assert callback["entity"] is None
    assert callback["evidence"] == [] and callback["recording_url"] is None
