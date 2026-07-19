

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
