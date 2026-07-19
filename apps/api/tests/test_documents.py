"""POST /documents/parse — reconciliation + flags over a canned extraction
(the OpenAI call is mocked; the live PDFs are exercised out-of-band)."""
import copy

import pytest
from fastapi.testclient import TestClient

from app import case_store, db
from app.fixtures import DEMO_CASE_ID, DEMO_LINE_ITEMS
from app.main import app
from app.routers import documents
from app.routers.documents import (
    _schema, case_reconciliation, parsed_flags, reconcile_bill, reconcile_eob,
)


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


# ── generalized pipeline (WS2): richer EOB extraction + case_store + real recon ──
def test_eob_schema_now_extracts_reconciliation_columns():
    """The EOB extraction schema populates the adjudication columns the reconciler
    needs (contract already supported them; extraction now fills them)."""
    props = _schema("eob")["schema"]["properties"]["line_items"]["items"]["properties"]
    assert {"units", "allowed_amount", "plan_paid", "patient_responsibility"} <= set(props)
    # the bill schema stays lean (no EOB-only columns)
    bill_props = _schema("bill")["schema"]["properties"]["line_items"]["items"]["properties"]
    assert "allowed_amount" not in bill_props


def _real_bill():
    return {"line_items": [
        {"cpt": "99283", "description": "ED visit", "date_of_service": "2026-06-02",
         "billed_amount": 2000.0, "dx_codes": []},
        {"cpt": "71046", "description": "CXR", "date_of_service": "2026-06-02",
         "billed_amount": 200.0, "dx_codes": []},
    ], "total_billed": 2200.0, "patient_balance": 900.0}


def _real_eob():
    return {"line_items": [
        {"cpt": "99283", "description": "ED visit", "date_of_service": "2026-06-02", "units": 1,
         "billed_amount": 2000.0, "allowed_amount": 500.0, "plan_paid": 500.0,
         "patient_responsibility": 0.0, "dx_codes": []},
    ], "total_billed": 2000.0, "patient_responsibility_total": 0.0}


def test_real_case_accumulates_both_docs_and_reconciles():
    case = "11111111-1111-1111-1111-111111111111"
    case_store.clear(case)
    # first the bill lands → no counterpart yet
    rec1 = case_reconciliation(case, _real_bill(), "bill")
    assert rec1["verdict"] == "pending_counterpart"
    case_store.put(case, "job_spec",
                   documents._splice(copy.deepcopy(documents._base_job_spec(case)), _real_bill(), "bill"))
    # then the EOB lands → real bill<->EOB reconciliation over the accumulated case
    rec2 = case_reconciliation(case, _real_eob(), "eob")
    assert rec2["verdict"] == "reconciled"
    assert [m["code"] for m in rec2["matched"]] == ["99283"]
    assert [b["code"] for b in rec2["bill_only"]] == ["71046"]  # phantom candidate
    case_store.clear(case)


def test_parsed_flags_for_real_case_uses_case_store_not_fixture():
    """A real case's flags come from its own accumulated spec, never Maya's fixture."""
    case = "22222222-2222-2222-2222-222222222222"
    case_store.clear(case)
    # accumulate the bill, then run flags with the EOB present → phantom on 71046
    case_store.put(case, "job_spec",
                   documents._splice(copy.deepcopy(documents._base_job_spec(case)), _real_bill(), "bill"))
    flags = parsed_flags(_real_eob(), "eob", case)
    types = {f.type for f in flags}
    assert "phantom" in types  # 71046 billed, never adjudicated on a covered date
    # Maya-only artifacts (upcode 99285) must NOT appear — we're not on the fixture
    assert not any(f.cpt == "99285" for f in flags)
    case_store.clear(case)


def test_demo_case_still_backed_by_fixture():
    """DEMO_CASE_ID keeps the pristine fixture spec (maya-compat path)."""
    case_store.clear(DEMO_CASE_ID)
    flags = parsed_flags(exact_bill_extraction(), "bill", DEMO_CASE_ID)
    assert {f.type for f in flags} == {"duplicate", "upcode", "unbundle", "eob_mismatch"}
