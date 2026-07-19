"""GET/POST /scenarios — the War Room scenario picker (generalized pipeline, WS3).

Builds a tiny synthetic scenario dir in tmp_path (data/scenarios/ doesn't
exist yet — WS4 hasn't landed the real suite) and points the router at it via
monkeypatch, exactly the "code defensively, empty list OK" contract in
docs/generalized-pipeline.md.
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app import case_store
from app.main import app
from app.routers import calls as calls_router
from app.routers import scenarios as scenarios_router
from app.simulator import build_generic_sequence


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_case_store():
    yield
    case_store.clear()


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def scenario_dir(tmp_path, monkeypatch):
    root = tmp_path / "scenarios"
    sc_dir = root / "sc01_test_case"
    scenario_json = {
        "scenario_id": "sc01_test_case",
        "archetype": "duplicate_charge",
        "title": "Synthetic duplicate-charge test scenario",
        "narrative": "A test bill with one duplicate line.",
        "hospital": {"name": "Synthetic Test Hospital"},
        "patient": {"name": "Sam Rivera", "dob": "1991-05-03", "account_number": "SYN-001"},
        "coverage": {"status": "insured", "payer_name": "Synthetic Payer",
                     "plan_name": "Synthetic PPO", "member_id": "SYN-M1"},
        "provider_entities": [{"name": "Synthetic Test Hospital", "entity_type": "facility"}],
        "answer_key_ref": "answer_key.json",
    }
    bill_json = {
        "line_items": [
            {"cpt": "71046", "description": "Chest X-ray", "date_of_service": "2026-02-01",
             "billed_amount": 400.0, "billing_entity": "facility"},
            {"cpt": "71046", "description": "Chest X-ray", "date_of_service": "2026-02-01",
             "billed_amount": 400.0, "billing_entity": "facility"},
        ],
        "patient_balance": 800.0,
    }
    eob_json = {
        "claim_number": "SYN-CLAIM-1",
        "patient_responsibility_total": 400.0,
        "denial_codes": [],
        "line_items": [],
    }
    answer_key_json = {
        "expected_flags": [
            {"type": "duplicate", "code": "71046", "dollar_impact": 400.0, "severity": "high",
             "detail": "71046 billed twice same date"},
        ],
        "benchmark_report": {
            "case_id": "placeholder",
            "hospital": "Synthetic Test Hospital",
            "lines": [{
                "code": "71046", "code_type": "CPT", "billed": 800.0, "units": 2,
                "anchors": [
                    {"method": "medicare", "value": 63.0, "source": "fixture",
                     "confidence": "high", "label": "Medicare"},
                ],
                "medicare_multiple": 6.35,
                "coverage": "full",
                "excess_above_band": 674.0,
            }],
            "totals": {"billed": 800.0, "medicare": 126.0, "fair_band_low": 126.0,
                       "fair_band_high": 320.0, "excess_above_band": 480.0,
                       "ask_anchor": 200.0, "ask_target": 260.0, "floor": 150.0},
            "data_version": {"chargemaster": "test", "medicare": "test", "config": "test"},
        },
        "provenance": {"generator": "test", "chargemaster_version": "test",
                       "medicare_version": "test"},
    }
    _write_json(sc_dir / "scenario.json", scenario_json)
    _write_json(sc_dir / "bill.json", bill_json)
    _write_json(sc_dir / "eob.json", eob_json)
    _write_json(sc_dir / "answer_key.json", answer_key_json)

    monkeypatch.setattr(scenarios_router, "SCENARIOS_DIR", root)
    return root


def test_list_scenarios_empty_before_suite_lands(client, tmp_path, monkeypatch):
    monkeypatch.setattr(scenarios_router, "SCENARIOS_DIR", tmp_path / "nope")
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    assert resp.json() == {"scenarios": []}


def test_list_scenarios_finds_the_synthetic_one(client, scenario_dir):
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    ids = [s["scenario_id"] for s in resp.json()["scenarios"]]
    assert "sc01_test_case" in ids


def test_load_unknown_scenario_404s(client, scenario_dir):
    resp = client.post("/scenarios/does_not_exist/load")
    assert resp.status_code == 404


def test_load_scenario_creates_a_case(client, scenario_dir):
    resp = client.post("/scenarios/sc01_test_case/load")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario_id"] == "sc01_test_case"
    case_id = body["case_id"]
    assert case_id

    case = client.get(f"/cases/{case_id}")
    assert case.status_code == 200
    spec = case.json()
    assert spec["patient"]["legal_name"] == "Sam Rivera"
    assert spec["bill"]["facility_name"] == "Synthetic Test Hospital"
    assert len(spec["bill"]["line_items"]) == 2
    assert spec["insurance"]["payer_name"] == "Synthetic Payer"

    flags = client.get(f"/cases/{case_id}/flags").json()["flags"]
    assert [f["type"] for f in flags] == ["duplicate"]
    assert flags[0]["cpt"] == "71046"
    assert flags[0]["dollar_impact"] == 400.0

    # allowed_numbers stored for the honesty audit (case_store slot)
    allowed = case_store.get(case_id, "allowed_numbers")
    assert 800.0 in allowed   # bill.patient_balance
    assert 400.0 in allowed   # dollar impact + line billed_amount
    assert 63.0 in allowed    # medicare anchor value from the answer key

    report = case_store.get(case_id, "benchmark_report")
    assert report["hospital"] == "Synthetic Test Hospital"

    assert case_store.get(case_id, "scenario_id") == "sc01_test_case"


def test_scenario_case_launches_simulated_calls_with_events(client, scenario_dir, monkeypatch):
    """B3: a scenario-loaded case can launch simulated calls end to end. launch
    used to 404 (spec_for_case only knew the fixtures); it now resolves the case
    the same way GET /cases does and schedules a sim whose sequence carries the
    War Room's events."""
    case_id = client.post("/scenarios/sc01_test_case/load").json()["case_id"]

    scheduled: list = []
    monkeypatch.setattr(calls_router, "play_calls", lambda specs: scheduled.extend(specs))

    resp = client.post("/calls/launch", json={"case_id": case_id, "simulate": True})
    assert resp.status_code == 200
    launched = resp.json()["launched"]
    assert launched and all(l["status"] == "queued" for l in launched)
    assert "Synthetic Test Hospital" in [l["entity"] for l in launched]
    for l in launched:
        uuid.UUID(l["call_id"])  # real uuid, not a stub

    # the sim was scheduled for THIS case, one spec per launched call
    assert scheduled and {s[2] for s in scheduled} == {case_id}
    assert len(scheduled) == len(launched)

    # the scheduled sim builds a real event stream for the scenario case
    call_id, _persona, sim_case_id, entity_name = scheduled[0]
    steps = build_generic_sequence(call_id, sim_case_id, entity_name)
    assert {"status", "event", "outcome"} <= {s["kind"] for s in steps}
    event_types = {s["type"] for s in steps if s["kind"] == "event"}
    assert {"transcript", "quote", "tool_call"} <= event_types


def test_scenario_case_rehydrates_after_restart(client, scenario_dir):
    """D1: case_store is process memory, but the scenario artifacts on disk are
    the source of truth. After a restart (simulated by clearing the store) the
    persisted case_id -> scenario_id index lets the next GET rebuild the case
    transparently — including the flags/benchmark slots and the launch path."""
    case_id = client.post("/scenarios/sc01_test_case/load").json()["case_id"]
    assert case_store.get_job_spec(case_id) is not None

    case_store.clear()  # fresh process: the in-memory store is empty
    assert case_store.get_job_spec(case_id) is None

    # GET transparently rehydrates the base spec from disk
    spec = client.get(f"/cases/{case_id}")
    assert spec.status_code == 200
    assert spec.json()["patient"]["legal_name"] == "Sam Rivera"
    assert spec.json()["bill"]["facility_name"] == "Synthetic Test Hospital"

    # and the dependent slots the endpoints read come back too
    assert case_store.get(case_id, "scenario_id") == "sc01_test_case"
    flags = client.get(f"/cases/{case_id}/flags").json()["flags"]
    assert [f["type"] for f in flags] == ["duplicate"]
    report = client.get(f"/cases/{case_id}/benchmark_report")
    assert report.status_code == 200
    assert report.json()["hospital"] == "Synthetic Test Hospital"

    # a launch after a restart resolves purely from disk (B3 + D1 together)
    case_store.clear()
    launch = client.post("/calls/launch", json={"case_id": case_id, "simulate": False})
    assert launch.status_code == 200
    assert launch.json()["launched"]

    # an unknown case that maps to no scenario still 404s (rehydration is scoped)
    assert client.get(f"/cases/{uuid.uuid4()}").status_code == 404
