"""Per-case ElevenLabs voice tools (generalized pipeline, WS3): get_benchmark
must serve a case's OWN stored benchmark_report, not the 5-CPT demo fixture,
once that case has one (scenario load / generalized pipeline)."""
import pytest
from fastapi.testclient import TestClient

from app import case_store, db
from app.main import app

CASE_ID = "22222222-2222-2222-2222-222222222222"
CALL_ID = "33333333-3333-3333-3333-333333333333"

REPORT = {
    "case_id": CASE_ID,
    "hospital": "Synthetic Test Hospital",
    "lines": [{
        "code": "71046",
        "code_type": "CPT",
        "billed": 800.0,
        "units": 2,
        "anchors": [
            {"method": "medicare", "value": 63.0, "source": "fixture",
             "confidence": "high", "label": "Medicare", "source_url": "https://example.test/medicare"},
            {"method": "cash_price", "value": 300.0, "source": "fixture",
             "confidence": "medium", "label": "cash price"},
            {"method": "cross_payer_band", "value": 250.0, "source": "fixture",
             "confidence": "medium", "label": "cross-payer median",
             "band": {"p25": 200.0, "median": 250.0, "p75": 310.0, "min": 180.0,
                      "max": 350.0, "n_payers": 4, "n_rows": 4}},
        ],
        "medicare_multiple": 6.35,
        "fair_band": {"low": 126.0, "high": 320.0, "basis": "medicare x multiple",
                      "low_multiple": 2.0, "high_multiple": 5.0},
        "coverage": "full",
        "excess_above_band": 480.0,
    }],
    "totals": {"billed": 800.0, "medicare": 126.0, "fair_band_low": 126.0,
               "fair_band_high": 320.0, "excess_above_band": 480.0,
               "ask_anchor": 200.0, "ask_target": 260.0, "floor": 150.0},
    "data_version": {"chargemaster": "test", "medicare": "test", "config": "test"},
}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_case_store():
    yield
    case_store.clear()


def test_get_benchmark_serves_stored_report_when_present(client, monkeypatch):
    case_store.put(CASE_ID, "benchmark_report", REPORT)
    monkeypatch.setattr(db, "get_call", lambda call_id: (
        {"id": CALL_ID, "case_id": CASE_ID} if call_id == CALL_ID else None))

    resp = client.post("/tools/get_benchmark", json={"cpt": "71046", "call_id": CALL_ID})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    bench = body["benchmark"]
    assert bench["cpt"] == "71046"
    assert bench["medicare_rate"] == 63.0
    assert bench["mrf_cash"] == 300.0
    assert bench["mrf_negotiated_median"] == 250.0
    assert bench["band_low"] == 200.0
    assert bench["band_high"] == 310.0
    assert bench["medicare_multiple"] == 6.35
    assert bench["coverage"] == "full"
    # NOT the demo fixture's medicare_rate for 71046 (63.0 happens to coincide
    # with the demo fixture in this test's numbers on purpose below — assert
    # against a code that ONLY exists in the stored report to prove no
    # fixture fallback happened)


def test_get_benchmark_unknown_code_in_stored_report_not_found(client, monkeypatch):
    case_store.put(CASE_ID, "benchmark_report", REPORT)
    monkeypatch.setattr(db, "get_call", lambda call_id: (
        {"id": CALL_ID, "case_id": CASE_ID} if call_id == CALL_ID else None))

    resp = client.post("/tools/get_benchmark", json={"cpt": "99999", "call_id": CALL_ID})
    assert resp.status_code == 200
    assert resp.json()["found"] is False


def test_get_benchmark_falls_back_to_demo_fixture_without_stored_report(client, monkeypatch):
    """No call_id / no case with a stored report -> exact prior behavior."""
    monkeypatch.setattr(db, "get_call", lambda call_id: None)
    resp = client.post("/tools/get_benchmark", json={"cpt": "71046"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["benchmark"]["medicare_rate"] == 63.0  # from data/seed/benchmarks_v0.json


def test_get_benchmark_case_without_stored_report_uses_fixture_fallback(client, monkeypatch):
    """A real call attached to a real case that HASN'T built a benchmark_report
    yet (e.g. Dan/Nina fixtures) must not error — falls back to the demo
    fixture exactly like the no-case path."""
    other_case = "44444444-4444-4444-4444-444444444444"
    monkeypatch.setattr(db, "get_call", lambda call_id: (
        {"id": CALL_ID, "case_id": other_case} if call_id == CALL_ID else None))
    resp = client.post("/tools/get_benchmark", json={"cpt": "71046", "call_id": CALL_ID})
    assert resp.status_code == 200
    assert resp.json()["found"] is True
    assert resp.json()["benchmark"]["medicare_rate"] == 63.0
