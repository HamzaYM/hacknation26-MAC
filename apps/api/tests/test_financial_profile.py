"""Voice-intake financial capture — POST /cases/{id}/financial-profile.

Covers: input validation, the overlay onto the served JobSpec (captured values
override the fixture), the no-op identity path (nothing captured → fixture dict
untouched, so the demo_flags cache + every fixture-only test stay green), and the
proof the captured lump-sum flows spec→dossier (floor == lump_sum_available).
"""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import load_vertical
from app.engine.dossier import build_dossier
from app.fixtures import DEMO_JOB_SPEC, demo_benchmarks
from app.fixtures_users import flags_for_spec, spec_for_case
from app.main import app
from app.models import JobSpec


@pytest.fixture(autouse=True)
def _fixture_only(monkeypatch):
    """Force fixture-only mode (in-process store, no Supabase) and isolate the
    captured-override store per test."""
    monkeypatch.setattr(db, "_get_conn", lambda: None)
    db._financial_overrides.clear()
    yield
    db._financial_overrides.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def test_post_overlays_served_spec(client):
    resp = client.post("/cases/demo/financial-profile",
                       json={"lump_sum_available": 2500, "monthly_max": 200})
    assert resp.status_code == 200
    body = resp.json()
    assert body["financial_profile"]["lump_sum_available"] == 2500
    assert body["financial_profile"]["max_monthly_payment"] == 200   # monthly_max mapped
    # fixture fields the interview didn't cover are preserved
    assert body["financial_profile"]["household_income"] == 39000

    # the served spec now reflects it (this is what /confirm reads)
    served = client.get("/cases/demo").json()
    assert served["financial_profile"]["lump_sum_available"] == 2500


def test_floor_flows_spec_to_dossier(client):
    """The judge-critical link: capture → served spec → dossier floor."""
    resp = client.post("/cases/demo/financial-profile", json={"lump_sum_available": 2500})
    assert resp.json()["floor"] == 2500          # response floor is the live dossier floor

    spec_dict = spec_for_case("demo")            # overlaid
    spec = JobSpec.model_validate(spec_dict)
    dossier = build_dossier(spec, flags_for_spec(spec_dict), demo_benchmarks(),
                            load_vertical(), entity=spec.entities[0])
    assert dossier.floor == 2500                 # was 1700 (the fixture) before capture


def test_no_capture_leaves_fixture_identity_intact():
    """Nothing captured → the exact fixture dict is returned (identity), so the
    demo_flags cache path and all existing fixture-only tests are unaffected."""
    assert spec_for_case("demo") is DEMO_JOB_SPEC


def test_validation_rejects_negative(client):
    assert client.post("/cases/demo/financial-profile",
                       json={"lump_sum_available": -5}).status_code == 422


def test_validation_rejects_non_number(client):
    assert client.post("/cases/demo/financial-profile",
                       json={"household_income": "lots"}).status_code == 422


def test_household_size_must_be_at_least_one(client):
    assert client.post("/cases/demo/financial-profile",
                       json={"household_size": 0}).status_code == 422


def test_empty_body_rejected(client):
    assert client.post("/cases/demo/financial-profile", json={}).status_code == 400


def test_unknown_case_404(client):
    assert client.post("/cases/nope/financial-profile",
                       json={"lump_sum_available": 100}).status_code == 404
