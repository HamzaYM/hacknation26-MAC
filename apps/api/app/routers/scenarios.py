"""Scenario endpoints — the War Room scenario picker.

GET /scenarios lists the suite (data/scenarios/<scenario_id>/scenario.json,
built by the scenario-generator workstream, contracts/scenario.schema.json).
POST /scenarios/{id}/load turns one scenario into a real case: reads its
bill.json/eob.json/answer_key.json artifacts, builds a JobSpec, and stores
everything (job_spec, flags, benchmark_report, allowed_numbers) in
case_store so the rest of the app — GET /cases/{id}, the per-case voice
tools, the honesty audit — serves it like any other case.

Coded defensively: data/scenarios/ not existing yet (before the scenario
suite lands) is not an error, it's an empty list. Individual scenario dirs
that are malformed are skipped, never a 500 for the whole listing.
"""
from __future__ import annotations

import json
import uuid as uuidlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from .. import case_store, db
from ..config import REPO_ROOT
from ..models import JobSpec

router = APIRouter()

SCENARIOS_DIR = REPO_ROOT / "data" / "scenarios"

# scenario.json expected_flags.type -> JobSpec derived_flags.type. The
# contract's flag taxonomy (contracts/scenario.schema.json) maps 1:1 onto
# models.DerivedFlag.type, except the NSA detector is named
# "nsa_balance_billing" in the scenario contract and emitted as "nsa" by the
# engine (integration unified the two NSA paths onto "nsa").
_FLAG_TYPE_MAP = {
    "duplicate": "duplicate",
    "upcode": "upcode",
    "unbundle": "unbundle",
    "phantom": "phantom",
    "eob_mismatch": "eob_mismatch",
    "nsa_balance_billing": "nsa",
    "markup": "markup",
    "denial": "denial",
    "units_error": "units_error",
    "absent_from_chargemaster": "absent_from_chargemaster",
}


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


@router.get("")
def list_scenarios() -> dict:
    """Every scenario found under data/scenarios/. Empty before the scenario
    suite lands, or on any dir that fails to read (skip, don't 500)."""
    scenarios: list[dict] = []
    if SCENARIOS_DIR.is_dir():
        for child in sorted(SCENARIOS_DIR.iterdir()):
            if not child.is_dir():
                continue
            meta = _load_json(child / "scenario.json")
            if meta is None:
                continue
            scenarios.append({
                "scenario_id": meta.get("scenario_id", child.name),
                "archetype": meta.get("archetype"),
                "title": meta.get("title"),
                "narrative": meta.get("narrative"),
                "hospital": meta.get("hospital"),
                "coverage": meta.get("coverage"),
            })
    return {"scenarios": scenarios}


def _default_patient(meta: dict) -> dict:
    p = meta.get("patient") or {}
    return {
        "legal_name": p.get("name") or "Scenario Patient",
        "dob": p.get("dob") or "1990-01-01",
    }


def _insurance_from_coverage(coverage: dict) -> dict:
    if not coverage or coverage.get("status") != "insured":
        return {}
    ins: dict = {}
    for src_key, dst_key in (("payer_name", "payer_name"), ("plan_name", "plan_type"),
                              ("member_id", "member_id")):
        if coverage.get(src_key):
            ins[dst_key] = coverage[src_key]
    return ins


def _entities_from_scenario(meta: dict, bill: dict) -> list[dict]:
    provider_entities = meta.get("provider_entities") or []
    if provider_entities:
        return [
            {
                "name": e.get("name"),
                # Entity.kind is a closed enum without a generic "professional"
                # option; facility maps directly, any professional entity
                # defaults to er_physician_group (the scenario generator can
                # override with a more specific kind by adding one directly
                # to entities in bill.json — see the entities fallback below).
                "kind": "facility" if e.get("entity_type") == "facility" else "er_physician_group",
                "balance": e.get("balance"),
            }
            for e in provider_entities if e.get("name")
        ]
    return [{
        "name": bill.get("facility_name", "Unknown Hospital"),
        "kind": "facility",
        "balance": bill.get("patient_balance"),
    }]


def _build_job_spec(case_id: str, meta: dict, bill: dict, eob: dict | None) -> dict:
    bill = dict(bill)
    bill.setdefault("facility_name", (meta.get("hospital") or {}).get("name", "Unknown Hospital"))
    bill.setdefault("account_number", (meta.get("patient") or {}).get("account_number", case_id[:8]))
    bill.setdefault("line_items", [])
    if bill.get("total_billed") is None:
        bill["total_billed"] = round(
            sum(float(li.get("billed_amount") or 0) for li in bill["line_items"]), 2)

    eob_out = eob or {"claim_number": None, "patient_responsibility_total": None,
                       "denial_codes": [], "line_items": []}

    return {
        "case_id": case_id,
        "patient": _default_patient(meta),
        "insurance": _insurance_from_coverage(meta.get("coverage") or {}),
        "financial_profile": {},
        "authorizations": {},
        "bill": bill,
        "eob": eob_out,
        "derived_flags": [],  # filled in by the caller from the answer key
        "entities": _entities_from_scenario(meta, bill),
    }


def _derived_flags_from_answer_key(expected_flags: list[dict] | None) -> list[dict]:
    out = []
    for f in expected_flags or []:
        mapped = _FLAG_TYPE_MAP.get(f.get("type"))
        if not mapped:
            continue
        code = f.get("code") or next(iter(f.get("codes") or []), None)
        out.append({
            "type": mapped,
            "cpt": code,
            "evidence": {"detail": f["detail"]} if f.get("detail") else {},
            "dollar_impact": f.get("dollar_impact") or 0.0,
        })
    return out


def _allowed_numbers_from_scenario(spec_dict: dict, answer_key: dict) -> list[float]:
    """Every number the answer key + resulting case make citable — becomes
    case_store's allowed_numbers slot, which webhooks._allowed_numbers_for_call
    reads for the per-case honesty audit."""
    nums: list[float] = []
    bill = spec_dict.get("bill") or {}
    for v in (bill.get("total_billed"), bill.get("patient_balance")):
        if v is not None:
            nums.append(float(v))
    eob = spec_dict.get("eob") or {}
    if eob.get("patient_responsibility_total") is not None:
        nums.append(float(eob["patient_responsibility_total"]))
    for li in bill.get("line_items", []):
        if li.get("billed_amount") is not None:
            nums.append(float(li["billed_amount"]))
        try:
            nums.append(float(li.get("cpt")))
        except (TypeError, ValueError):
            pass
    for f in answer_key.get("expected_flags") or []:
        if f.get("dollar_impact") is not None:
            nums.append(float(f["dollar_impact"]))
    report = answer_key.get("benchmark_report") or {}
    totals = report.get("totals") or {}
    for v in totals.values():
        if isinstance(v, (int, float)):
            nums.append(float(v))
    for line in report.get("lines") or []:
        if line.get("billed") is not None:
            nums.append(float(line["billed"]))
        try:
            nums.append(float(line.get("code")))
        except (TypeError, ValueError):
            pass
        for anchor in line.get("anchors") or []:
            if isinstance(anchor.get("value"), (int, float)):
                nums.append(float(anchor["value"]))
        fair_band = line.get("fair_band") or {}
        for key in ("low", "high"):
            if isinstance(fair_band.get(key), (int, float)):
                nums.append(float(fair_band[key]))
    return nums


def _hydrate_case(case_id: str, scenario_id: str) -> dict | None:
    """Build a case's JobSpec from a scenario's on-disk artifacts (the
    deterministic source of truth) and populate every case_store slot for it.
    Returns the JobSpec dict, or None when the scenario is missing/unreadable.
    Shared by POST /{id}/load and the post-restart rehydration path (D1)."""
    scenario_dir = SCENARIOS_DIR / scenario_id
    meta = _load_json(scenario_dir / "scenario.json")
    if meta is None:
        return None

    bill = _load_json(scenario_dir / "bill.json") or {}
    eob = _load_json(scenario_dir / "eob.json")
    answer_key_ref = meta.get("answer_key_ref") or "answer_key.json"
    answer_key = (_load_json(scenario_dir / answer_key_ref)
                  or _load_json(scenario_dir / "answer_key.json") or {})

    spec_dict = _build_job_spec(case_id, meta, bill, eob)
    flags = _derived_flags_from_answer_key(answer_key.get("expected_flags"))
    spec_dict["derived_flags"] = flags

    case_store.put(case_id, "job_spec", spec_dict)
    case_store.put(case_id, "scenario_id", scenario_id)
    case_store.put(case_id, "answer_key", answer_key)
    case_store.put(case_id, "flags", flags)
    benchmark_report = answer_key.get("benchmark_report")
    if benchmark_report:
        case_store.put(case_id, "benchmark_report", benchmark_report)
    case_store.put(case_id, "allowed_numbers", _allowed_numbers_from_scenario(spec_dict, answer_key))
    return spec_dict


# case_id -> scenario_id index, persisted beside the suite as a hidden file (not
# a scenario dir, so list_scenarios skips it). case_store is process memory; the
# scenario artifacts on disk are deterministic, so a loaded case survives an API
# restart by persisting only this mapping and REHYDRATING case_store on a miss (D1).
def _case_index_path() -> Path:
    return SCENARIOS_DIR / ".case_index.json"


def _read_case_index() -> dict:
    data = _load_json(_case_index_path())
    return data if isinstance(data, dict) else {}


def _remember_scenario_case(case_id: str, scenario_id: str) -> None:
    """Persist the case_id -> scenario_id mapping. Best-effort: a write failure
    (read-only fs, etc.) is swallowed and never blocks a scenario load."""
    try:
        index = _read_case_index()
        index[case_id] = scenario_id
        path = _case_index_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(index), encoding="utf-8")
    except OSError:
        pass


def rehydrate_case(case_id: str) -> dict | None:
    """Rebuild a scenario-loaded case in case_store from its on-disk artifacts
    when it's absent from memory — e.g. after an API restart (D1). Returns the
    JobSpec dict, or None when case_id isn't a known scenario case."""
    scenario_id = _read_case_index().get(case_id)
    if scenario_id is None:
        return None
    return _hydrate_case(case_id, scenario_id)


@router.post("/{scenario_id}/load")
def load_scenario(scenario_id: str) -> dict:
    """Create a case from a scenario's artifacts. Returns {"case_id", "scenario_id"}."""
    case_id = str(uuidlib.uuid4())
    spec_dict = _hydrate_case(case_id, scenario_id)
    if spec_dict is None:
        raise HTTPException(404, f"scenario {scenario_id!r} not found")

    try:
        JobSpec.model_validate(spec_dict)
    except Exception as err:  # noqa: BLE001 — a malformed scenario is a 422, not a 500
        case_store.clear(case_id)  # don't leave a half-built case behind
        raise HTTPException(422, f"scenario {scenario_id!r} produced an invalid case: {err}") from err

    _remember_scenario_case(case_id, scenario_id)  # survive an API restart (D1)
    db.ensure_case(case_id, spec_dict, None)  # best-effort
    db.record_scenario_load(case_id, scenario_id)  # best-effort

    return {"case_id": case_id, "scenario_id": scenario_id}
