"""POST /documents/parse — reconciliation + flags over a canned extraction
(the OpenAI call is mocked; the live PDFs are exercised out-of-band)."""
import copy

import pytest
from fastapi.testclient import TestClient

from app import db
from app.fixtures import DEMO_LINE_ITEMS
from app.main import app
from app.routers import documents
from app.routers.documents import parsed_flags, reconcile_bill, reconcile_eob


def exact_bill_extraction() -> dict:
    """What a perfect vision parse of mercy_general_bill.pdf returns."""
    return {
        "line_items": copy.deepcopy(DEMO_LINE_ITEMS),
        "total_billed": 8432.00,
        "patient_balance": 4287.00,
    }


# ── reconciliation ────────────────────────────────────────────────────────
def test_exact_extraction_reconciles_exact():
    rec = reconcile_bill(exact_bill_extraction())
    assert rec == {"verdict": "exact", "matches": 23, "mismatches": []}


def test_wrong_amount_is_partial_with_field_mismatch():
    parsed = exact_bill_extraction()
    parsed["line_items"][0]["billed_amount"] = 2340.99  # the 99285 line
    rec = reconcile_bill(parsed)
    assert rec["verdict"] == "partial"
    assert rec["matches"] == 22
    assert {"cpt": "99285", "field": "billed_amount",
            "parsed": 2340.99, "expected": 2340.00} in rec["mismatches"]


def test_missing_and_extra_lines_and_totals_mismatch():
    parsed = exact_bill_extraction()
    del parsed["line_items"][1]  # drop one 71046 duplicate
    parsed["line_items"].append({"cpt": "99999", "description": "phantom",
                                 "date_of_service": "2026-06-02", "billed_amount": 10.0,
                                 "dx_codes": []})
    parsed["total_billed"] = 8030.00
    rec = reconcile_bill(parsed)
    assert rec["verdict"] == "partial"
    fields = {(m["cpt"], m["field"]) for m in rec["mismatches"]}
    assert ("71046", "line_item") in fields          # missing duplicate
    assert ("99999", "line_item") in fields          # unexpected extra
    assert (None, "total_billed") in fields          # totals compared too


def test_garbage_extraction_fails():
    rec = reconcile_bill({"line_items": [], "total_billed": 0, "patient_balance": 0})
    assert rec["verdict"] == "failed" and rec["matches"] == 0


def test_eob_reconciles_against_fixture_total():
    assert reconcile_eob({"patient_responsibility_total": 3875.00}) == {
        "verdict": "exact", "matches": 1, "mismatches": []}
    rec = reconcile_eob({"patient_responsibility_total": 3999.00})
    assert rec["verdict"] == "failed"
    assert rec["mismatches"][0]["expected"] == 3875.00


# ── real engine flags over parsed data ────────────────────────────────────
def test_all_four_demo_flags_fire_on_parsed_bill():
    flags = parsed_flags(exact_bill_extraction(), "bill")
    assert {f.type: f.dollar_impact for f in flags} == {
        "duplicate": 412.00, "upcode": 2011.21, "unbundle": 642.00, "eob_mismatch": 412.00}


def test_flags_react_to_parsed_data_not_fixture():
    parsed = exact_bill_extraction()
    parsed["line_items"] = [li for li in parsed["line_items"] if li["cpt"] != "71046"][:1]
    parsed["patient_balance"] = 3875.00  # matches the EOB → no mismatch either
    types = {f.type for f in parsed_flags(parsed, "bill")}
    assert "duplicate" not in types and "eob_mismatch" not in types


# ── endpoint contract ─────────────────────────────────────────────────────
@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(db, "_get_conn", lambda: None)          # no-op persistence
    monkeypatch.setattr(documents.storage, "store_document", lambda path, data: None)
    monkeypatch.setattr(documents, "extract_pdf",
                        lambda pdf_bytes, kind: (exact_bill_extraction(), "gpt-test"))
    return TestClient(app)


def test_parse_endpoint_contract_shape(client):
    resp = client.post("/documents/parse",
                       files={"file": ("bill.pdf", b"%PDF-1.4 fake", "application/pdf")},
                       data={"kind": "bill"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"document_id", "storage_path", "parsed", "reconciliation", "flags"}
    assert body["storage_path"].startswith("documents/")
    assert body["reconciliation"]["verdict"] == "exact"
    assert [f["type"] for f in body["flags"]] == ["duplicate", "upcode", "unbundle", "eob_mismatch"]
    assert body["parsed"]["patient_balance"] == 4287.00


def test_parse_endpoint_rejects_bad_kind_and_empty_file(client):
    resp = client.post("/documents/parse",
                       files={"file": ("x.pdf", b"%PDF", "application/pdf")},
                       data={"kind": "invoice"})
    assert resp.status_code == 422
    resp = client.post("/documents/parse",
                       files={"file": ("x.pdf", b"", "application/pdf")},
                       data={"kind": "bill"})
    assert resp.status_code == 422
