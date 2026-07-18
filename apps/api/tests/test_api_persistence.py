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
