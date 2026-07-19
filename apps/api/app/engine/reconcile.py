"""Line-level bill <-> EOB reconciliation — deterministic, pure code.

Stage 2 of the generalized pipeline (docs/generalized-pipeline.md): given a
parsed bill and a parsed EOB (or None, for self-pay), match line items and
classify each as matched / bill_only / eob_only, computing per-line and total
billed vs. allowed vs. plan_paid vs. patient_responsibility deltas.

No LLM, no database — this is a plain function the flag detectors and the
documents router both consume. Every number it emits is arithmetic over the
two structured documents it was handed.

Matching (a bill line may legitimately repeat — duplicates, multi-unit days —
so matching is greedy over unconsumed EOB lines, most-specific key first):
  1. (code, date_of_service, units)
  2. (code, date_of_service)
  3. (code)
The `match_basis` field records which key matched, so callers (e.g. the
units_error detector) can tell an exact match from a looser one.
"""
from __future__ import annotations

from typing import Any


def _num(x: Any) -> float | None:
    return None if x is None else round(float(x), 2)


def _line_view(li: Any) -> dict:
    """Normalize a LineItem (pydantic) or plain dict into the reconciliation view."""
    get = (lambda k, d=None: getattr(li, k, d)) if not isinstance(li, dict) else li.get
    return {
        "code": get("cpt"),
        "date": get("date_of_service"),
        "units": get("units") if get("units") is not None else 1,
        "description": get("description"),
        "billing_entity": get("billing_entity"),
        "billed": _num(get("billed_amount")),
        "allowed": _num(get("allowed_amount")),
        "plan_paid": _num(get("plan_paid")),
        "patient_responsibility": _num(get("patient_responsibility")),
    }


def _sum(views: list[dict], key: str) -> float | None:
    vals = [v[key] for v in views if v.get(key) is not None]
    return round(sum(vals), 2) if vals else None


def _find_match(bill_v: dict, eob_views: list[dict], used: set[int]) -> tuple[int | None, str | None]:
    """Index of the best unconsumed EOB line + the key that matched."""
    keys = [
        ("code+date+units", lambda e: e["code"] == bill_v["code"]
         and e["date"] == bill_v["date"] and e["units"] == bill_v["units"]),
        ("code+date", lambda e: e["code"] == bill_v["code"] and e["date"] == bill_v["date"]),
        ("code", lambda e: e["code"] == bill_v["code"]),
    ]
    for basis, pred in keys:
        for i, e in enumerate(eob_views):
            if i not in used and pred(e):
                return i, basis
    return None, None


def reconcile(bill: Any, eob: Any | None) -> dict:
    """Reconcile a bill against an EOB. `bill`/`eob` are Bill/Eob pydantic models
    (or dicts with the same shape). `eob=None` means self-pay: no adjudication to
    reconcile against, so every bill line is bill_only.

    Returns a dict (see module docstring) with `matched`, `bill_only`,
    `eob_only`, `totals`, and `self_pay`.
    """
    bget = (lambda k, d=None: getattr(bill, k, d)) if not isinstance(bill, dict) else bill.get
    bill_lines = bget("line_items") or []
    bill_views = [_line_view(li) for li in bill_lines]
    bill_patient_balance = _num(bget("patient_balance"))
    bill_total_billed = _num(bget("total_billed"))

    self_pay = eob is None
    if self_pay:
        eob_views: list[dict] = []
        eob_patient_resp_total = None
        eob_total_billed = None
        eob_dates: set = set()
    else:
        eget = (lambda k, d=None: getattr(eob, k, d)) if not isinstance(eob, dict) else eob.get
        eob_views = [_line_view(li) for li in (eget("line_items") or [])]
        eob_patient_resp_total = _num(eget("patient_responsibility_total"))
        eob_total_billed = _num(eget("total_billed"))
        eob_dates = {e["date"] for e in eob_views if e["date"] is not None}

    matched: list[dict] = []
    bill_only: list[dict] = []
    used: set[int] = set()

    for bv in bill_views:
        idx, basis = (None, None) if self_pay else _find_match(bv, eob_views, used)
        if idx is None:
            row = dict(bv)
            # a bill_only line is a phantom candidate only if the EOB otherwise
            # covers that service date (see flags.phantom).
            row["eob_covers_date"] = (not self_pay) and (bv["date"] in eob_dates)
            bill_only.append(row)
            continue
        used.add(idx)
        ev = eob_views[idx]
        matched.append({
            "code": bv["code"],
            "date": bv["date"],
            "match_basis": basis,
            "units_bill": bv["units"],
            "units_eob": ev["units"],
            "billed": bv["billed"],
            "allowed": ev["allowed"],
            "plan_paid": ev["plan_paid"],
            "patient_responsibility": ev["patient_responsibility"],
            "billed_vs_allowed": (round(bv["billed"] - ev["allowed"], 2)
                                  if bv["billed"] is not None and ev["allowed"] is not None else None),
            "billing_entity": bv["billing_entity"],
        })

    eob_only = [dict(e) for i, e in enumerate(eob_views) if i not in used]

    pr_delta = None
    if bill_patient_balance is not None and eob_patient_resp_total is not None:
        pr_delta = round(bill_patient_balance - eob_patient_resp_total, 2)

    totals = {
        "bill_billed": _sum(bill_views, "billed") or bill_total_billed,
        "bill_patient_balance": bill_patient_balance,
        "eob_billed": _sum(eob_views, "billed") or eob_total_billed,
        "eob_allowed": _sum(eob_views, "allowed"),
        "eob_plan_paid": _sum(eob_views, "plan_paid"),
        "eob_patient_responsibility": eob_patient_resp_total or _sum(eob_views, "patient_responsibility"),
        "patient_responsibility_delta": pr_delta,
        "matched_count": len(matched),
        "bill_only_count": len(bill_only),
        "eob_only_count": len(eob_only),
    }

    return {
        "self_pay": self_pay,
        "matched": matched,
        "bill_only": bill_only,
        "eob_only": eob_only,
        "totals": totals,
    }
