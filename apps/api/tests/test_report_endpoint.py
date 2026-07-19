

def test_achieved_column_only_uses_facility_settlements(monkeypatch):
    """A collections settlement (different entity) must not fill the facility
    lines' achieved column (accuracy-audit finding)."""
    from app import db
    from app.routers.cases import get_case_report
    monkeypatch.setattr(db, "get_case_outcomes", lambda cid: [
        {"outcome_type": "reduction", "target_entity": "Meridian Recovery Services",
         "original_amount": 980, "final_amount": 392, "reduction_pct": 60.0},
    ])
    monkeypatch.setattr(db, "get_events_by_ids", lambda ids: [])
    report = get_case_report("demo")
    assert all(line.get("achieved") is None for line in report["lines"])

    monkeypatch.setattr(db, "get_case_outcomes", lambda cid: [
        {"outcome_type": "reduction", "target_entity": "Mercy General Hospital",
         "original_amount": 4287, "final_amount": 1650, "reduction_pct": 61.5},
    ])
    report = get_case_report("demo")
    assert any(line.get("achieved") for line in report["lines"])


def test_report_passes_through_account_and_claim_numbers(monkeypatch):
    """The case view reads the bill account # and EOB claim # off the report."""
    from app import db
    from app.routers.cases import get_case_report
    monkeypatch.setattr(db, "get_case_outcomes", lambda cid: [])
    report = get_case_report("demo")
    assert report["account_number"] == "MG-4471983"
    assert report["claim_number"] == "BCBSMA-2026-118842"


def test_report_maps_call_ended_at_to_resolved_at(monkeypatch):
    """Each outcome's resolved_at comes from its call's ended_at (no column add),
    and the raw ended_at is not leaked into the response."""
    from app import db
    from app.routers.cases import get_case_report
    monkeypatch.setattr(db, "get_case_outcomes", lambda cid: [
        {"outcome_type": "reduction", "target_entity": "Meridian Recovery Services",
         "original_amount": 980, "final_amount": 392, "reduction_pct": 60.0,
         "ended_at": "2026-07-18T22:51:00+00:00"},
    ])
    monkeypatch.setattr(db, "get_events_by_ids", lambda ids: [])
    report = get_case_report("demo")
    outcome = report["outcomes"][0]
    assert outcome["resolved_at"] == "2026-07-18T22:51:00+00:00"
    assert "ended_at" not in outcome


def test_action_plan_endpoint_returns_200(monkeypatch):
    """Probe finding: /cases/{id}/action_plan 500'd on every request —
    undefined _require_demo + un-imported demo_flags in the route body."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/cases/demo/action_plan?no_llm=true")
    assert resp.status_code == 200
    body = resp.json()
    assert "input" in body and "copy" in body


def test_recommendation_dedupes_by_entity():
    from app.engine.report import build_recommendation
    ranked = [
        {"outcome_type": "reduction", "target_entity": "Meridian", "final_amount": 392, "original_amount": 980},
        {"outcome_type": "reduction", "target_entity": "Meridian", "final_amount": 392, "original_amount": 980},
        {"outcome_type": "documented_decline", "target_entity": "Mercy"},
        {"outcome_type": "documented_decline", "target_entity": "Mercy"},
        {"outcome_type": "documented_decline", "target_entity": "Mercy"},
    ]
    rec = build_recommendation(ranked)
    assert rec.count("Meridian") == 1
    assert rec.count("Mercy") == 1
