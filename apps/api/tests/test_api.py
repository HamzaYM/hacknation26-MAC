"""API wiring smoke tests — the stub response shapes stay backward-compatible."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_get_demo_case(client):
    resp = client.get("/cases/demo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["bill"]["patient_balance"] == 4287.00
    assert len(body["bill"]["line_items"]) == 23


def test_get_case_flags_endpoint(client):
    resp = client.get("/cases/demo/flags")
    assert resp.status_code == 200
    flags = resp.json()["flags"]
    assert [f["type"] for f in flags] == ["duplicate", "upcode", "unbundle", "eob_mismatch"]
    assert client.get("/cases/nope/flags").status_code == 404


def test_get_case_brief_serves_computed_flags(client):
    resp = client.post("/tools/get_case_brief", json={})
    assert resp.status_code == 200
    spec = resp.json()["job_spec"]
    assert {f["type"]: f["dollar_impact"] for f in spec["derived_flags"]} == {
        "duplicate": 412.00, "upcode": 2011.21, "unbundle": 642.00, "eob_mismatch": 412.00,
    }


def test_report_lever_result_uses_the_real_state_machine(client):
    body = {"call_id": "api-call-1", "lever": "open_and_hold_account", "result": "accepted"}
    resp = client.post("/tools/report_lever_result", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_move"] == "reach_authority"   # backward-compatible key
    assert "notes" in data                          # backward-compatible key
    # stonewall phrase steering: two unhedged stonewalls on the same lever PARK it
    # and move on (escalation is a last resort now — no jump to a supervisor).
    for _ in range(2):
        resp = client.post("/tools/report_lever_result", json={
            "call_id": "api-call-1", "lever": "line_item_disputes", "result": "rejected",
            "quote": "we don't negotiate",
        })
    data = resp.json()
    assert data["parked"]["lever"] == "line_item_disputes"
    assert data["next_move"] != "line_item_disputes"


def test_get_benchmark_still_answers(client):
    resp = client.post("/tools/get_benchmark", json={"cpt": "71046"})
    assert resp.json()["found"] is True
    assert resp.json()["benchmark"]["medicare_rate"] == 63.0
