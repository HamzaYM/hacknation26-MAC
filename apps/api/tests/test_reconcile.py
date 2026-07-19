"""engine/reconcile.py — line-level bill<->EOB reconciliation.

Pure arithmetic over two structured documents: match lines, classify
matched/bill_only/eob_only, per-line billed-vs-allowed deltas, totals, and the
self-pay (eob=None) path.
"""
from app.engine.reconcile import reconcile
from app.models import Bill, Eob, LineItem


def _bill(lines, **kw):
    return Bill(facility_name=kw.get("facility_name", "H"), account_number="A1",
                total_billed=kw.get("total_billed"), patient_balance=kw.get("patient_balance"),
                line_items=[LineItem(**li) for li in lines])


def _eob(lines, **kw):
    return Eob(patient_responsibility_total=kw.get("patient_responsibility_total"),
               denial_codes=kw.get("denial_codes", []),
               line_items=[LineItem(**li) for li in lines])


D = "2026-06-02"


def test_matched_line_carries_all_deltas():
    bill = _bill([{"cpt": "99283", "date_of_service": D, "units": 1, "billed_amount": 300.0}])
    eob = _eob([{"cpt": "99283", "date_of_service": D, "units": 1, "billed_amount": 300.0,
                 "allowed_amount": 245.0, "plan_paid": 200.0, "patient_responsibility": 45.0}])
    r = reconcile(bill, eob)
    assert not r["self_pay"]
    assert len(r["matched"]) == 1 and not r["bill_only"] and not r["eob_only"]
    m = r["matched"][0]
    assert m["match_basis"] == "code+date+units"
    assert m["billed"] == 300.0 and m["allowed"] == 245.0
    assert m["plan_paid"] == 200.0 and m["patient_responsibility"] == 45.0
    assert m["billed_vs_allowed"] == 55.0


def test_bill_only_and_eob_only_classification():
    bill = _bill([
        {"cpt": "99283", "date_of_service": D, "billed_amount": 300.0},
        {"cpt": "71046", "date_of_service": D, "billed_amount": 200.0},  # not on EOB
    ])
    eob = _eob([
        {"cpt": "99283", "date_of_service": D, "billed_amount": 300.0, "allowed_amount": 245.0,
         "plan_paid": 245.0, "patient_responsibility": 0.0},
        {"cpt": "80053", "date_of_service": D, "billed_amount": 48.0, "allowed_amount": 40.0,
         "plan_paid": 40.0, "patient_responsibility": 0.0},  # not on bill
    ])
    r = reconcile(bill, eob)
    assert [m["code"] for m in r["matched"]] == ["99283"]
    assert [b["code"] for b in r["bill_only"]] == ["71046"]
    assert [e["code"] for e in r["eob_only"]] == ["80053"]
    # the bill_only 71046 falls on a date the EOB adjudicated → phantom candidate
    assert r["bill_only"][0]["eob_covers_date"] is True


def test_duplicate_bill_lines_consume_one_eob_line_each():
    bill = _bill([
        {"cpt": "71046", "date_of_service": D, "billed_amount": 412.0},
        {"cpt": "71046", "date_of_service": D, "billed_amount": 412.0},  # duplicate
    ])
    eob = _eob([{"cpt": "71046", "date_of_service": D, "billed_amount": 412.0,
                 "allowed_amount": 180.0, "plan_paid": 180.0, "patient_responsibility": 0.0}])
    r = reconcile(bill, eob)
    assert len(r["matched"]) == 1 and len(r["bill_only"]) == 1
    assert r["bill_only"][0]["code"] == "71046"


def test_fallback_match_basis_when_units_differ():
    bill = _bill([{"cpt": "96374", "date_of_service": D, "units": 3, "billed_amount": 300.0}])
    eob = _eob([{"cpt": "96374", "date_of_service": D, "units": 1, "billed_amount": 300.0,
                 "allowed_amount": 104.0, "plan_paid": 104.0, "patient_responsibility": 0.0}])
    r = reconcile(bill, eob)
    assert r["matched"][0]["match_basis"] == "code+date"
    assert r["matched"][0]["units_bill"] == 3 and r["matched"][0]["units_eob"] == 1


def test_self_pay_puts_everything_in_bill_only():
    bill = _bill([
        {"cpt": "99283", "date_of_service": D, "billed_amount": 300.0},
        {"cpt": "71046", "date_of_service": D, "billed_amount": 200.0},
    ], patient_balance=500.0)
    r = reconcile(bill, None)
    assert r["self_pay"] is True
    assert len(r["bill_only"]) == 2 and not r["matched"] and not r["eob_only"]
    # no EOB → never a phantom candidate
    assert all(b["eob_covers_date"] is False for b in r["bill_only"])
    assert r["totals"]["eob_patient_responsibility"] is None


def test_totals_and_patient_responsibility_delta():
    bill = _bill([{"cpt": "99283", "date_of_service": D, "billed_amount": 300.0}],
                 patient_balance=100.0)
    eob = _eob([{"cpt": "99283", "date_of_service": D, "billed_amount": 300.0, "allowed_amount": 245.0,
                 "plan_paid": 200.0, "patient_responsibility": 45.0}],
               patient_responsibility_total=45.0)
    r = reconcile(bill, eob)
    t = r["totals"]
    assert t["bill_patient_balance"] == 100.0
    assert t["eob_patient_responsibility"] == 45.0
    assert t["patient_responsibility_delta"] == 55.0  # bill bills 55 more than the EOB says is owed
    assert t["eob_allowed"] == 245.0 and t["eob_plan_paid"] == 200.0
