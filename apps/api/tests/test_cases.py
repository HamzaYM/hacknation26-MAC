"""POST /cases + case_store-backed GET /cases/{id} (generalized pipeline, WS3)."""
import pytest
from fastapi.testclient import TestClient

from app import case_store
from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_case_store():
    yield
    case_store.clear()


def _job_spec_body(case_id: str | None = None) -> dict:
    body = {
        "patient": {"legal_name": "Jordan Lee", "dob": "1988-02-11"},
        "insurance": {"payer_name": "Test Payer"},
        "bill": {
            "facility_name": "Test General Hospital",
            "account_number": "TGH-0001",
            "total_billed": 500.0,
            "patient_balance": 500.0,
            "line_items": [
                {"cpt": "99283", "billed_amount": 500.0, "date_of_service": "2026-01-01"},
            ],
        },
        "eob": {"claim_number": None, "patient_responsibility_total": None,
                "denial_codes": [], "line_items": []},
        "entities": [{"name": "Test General Hospital", "kind": "facility", "balance": 500.0}],
    }
    if case_id:
        body["case_id"] = case_id
    return body


def test_create_case_roundtrip(client):
    resp = client.post("/cases", json=_job_spec_body())
    assert resp.status_code == 200
    case_id = resp.json()["case_id"]
    assert case_id

    got = client.get(f"/cases/{case_id}")
    assert got.status_code == 200
    body = got.json()
    assert body["case_id"] == case_id
    assert body["patient"]["legal_name"] == "Jordan Lee"
    assert body["bill"]["facility_name"] == "Test General Hospital"
    assert body["bill"]["line_items"][0]["cpt"] == "99283"


def test_create_case_honors_supplied_case_id(client):
    supplied = "11111111-1111-1111-1111-111111111111"
    resp = client.post("/cases", json=_job_spec_body(case_id=supplied))
    assert resp.status_code == 200
    assert resp.json()["case_id"] == supplied
    assert client.get(f"/cases/{supplied}").json()["case_id"] == supplied


def test_create_case_missing_patient_dob_rejected(client):
    body = _job_spec_body()
    body["patient"] = {"legal_name": "No DOB"}
    resp = client.post("/cases", json=body)
    assert resp.status_code == 422


def test_create_case_missing_bill_rejected(client):
    body = _job_spec_body()
    del body["bill"]
    resp = client.post("/cases", json=body)
    assert resp.status_code == 422


def test_get_unknown_case_still_404s(client):
    assert client.get("/cases/does-not-exist").status_code == 404


def test_created_case_flags_endpoint_does_not_500(client):
    """No engine crash for a case whose codes aren't in the 5-CPT demo
    fixture — flags_for_spec degrades to whatever the generic detector finds
    (possibly empty), never an error."""
    resp = client.post("/cases", json=_job_spec_body())
    case_id = resp.json()["case_id"]
    got = client.get(f"/cases/{case_id}/flags")
    assert got.status_code == 200
    assert got.json()["case_id"] == case_id
    assert isinstance(got.json()["flags"], list)


def test_demo_case_still_works_unaffected(client):
    """POST /cases must not disturb the fixture-served demo path."""
    resp = client.get("/cases/demo")
    assert resp.status_code == 200
    assert resp.json()["bill"]["patient_balance"] == 4287.00
