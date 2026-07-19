"""Action-plan INPUT assembler — the code-computed payload the copywriter turns
into user-facing text (prompts/action_plan.md defines this exact shape).

PRD §7 boundary: every number, date, statute, and dollar figure here is computed
by the engine or copied verbatim from J's data (benchmarks + config/levers.json).
The copywriter (app/action_plan_copy.py) may only rephrase these values; it never
computes or invents. This module is that guarantee's source of truth.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import levers as levers_mod
from .dossier import build_dossier, corrected_cpt_set


def _totals(cpts: set[str], benchmarks: dict) -> dict:
    def _sum(key: str) -> float:
        return round(sum(benchmarks[c][key] for c in cpts
                         if benchmarks[c].get(key) is not None), 2)
    return {
        "medicare_total": _sum("medicare_rate"),
        "mrf_cash_total": _sum("mrf_cash"),
        "mrf_negotiated_median_total": _sum("mrf_negotiated_median"),
    }


def _plain(flag, benchmarks: dict) -> str:
    """One plain-English line per flag — no numbers (the copy carries those)."""
    if flag.type == "duplicate":
        name = (benchmarks.get(flag.cpt, {}).get("description") or "a charge").split(" (")[0].lower()
        return f"{name} (code {flag.cpt}) billed twice on the same date"
    if flag.type == "upcode":
        return "the ER visit was billed at a higher level than the diagnosis supports"
    if flag.type == "unbundle":
        return "a lab panel was split into separate line items instead of the cheaper bundled code"
    if flag.type == "eob_mismatch":
        return "the bill is higher than what your insurer's statement says you owe"
    return flag.type.replace("_", " ")


def _add_days(iso: str | None, days: int) -> str | None:
    if not iso:
        return None
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


# window params read from J's statute pack (config/levers.json) so the dates
# track the same source the citations do.
def _lever_param(pack_id: str, key: str, default: int) -> int:
    for lv in levers_mod.load_levers():
        if lv["lever_id"] == pack_id:
            return lv.get("parameters", {}).get(key, default)
    return default


def build_action_plan_input(job_spec, flags: list, benchmarks: dict, config: dict) -> dict:
    """The exact input JSON prompts/action_plan.md consumes — all fields code-computed."""
    bill = job_spec.bill
    balance = bill.patient_balance
    cpts = corrected_cpt_set(job_spec, flags, benchmarks)
    totals = _totals(cpts, benchmarks)

    # primary target dossier gives anchor/target for the savings band
    primary = job_spec.entities[0]
    dossier = build_dossier(job_spec, flags, benchmarks, config, entity=primary)

    # savings = dollars OFF the balance. Conservative: pay down to the hospital's
    # posted cash price. Optimistic: settle to the self-pay target. Both computed
    # from the dossier; the demo's $1,650 settlement sits inside this band.
    save_low = round(balance - totals["mrf_cash_total"], 2) if totals["mrf_cash_total"] else None
    save_high = round(balance - dossier.target, 2)
    savings_estimate = {"low": save_low, "high": save_high, "confidence": "medium"}

    armed_provider = levers_mod.armed_levers(job_spec, flags, benchmarks, "provider", totals)
    armed_collections = levers_mod.armed_levers(job_spec, flags, benchmarks, "collections", totals)
    provider_ids = [l["id"] for l in armed_provider]
    collections_ids = [l["id"] for l in armed_collections]

    # boost opportunities — facts that would unlock a bigger lever, qualifier
    # carried verbatim from the pack's parameters (stays [directional]).
    boosts: list[dict] = []
    charity = next((l for l in armed_provider if l["id"] == "501r_charity_care"), None)
    if charity:
        rng = charity.get("parameters", {}).get("typical_discount_range", "50-100%")
        boosts.append({
            "missing": "income_proof",
            "unlocks_lever": "charity_care",
            "impact_note": f"{rng} reduction if you qualify [directional]",
        })

    planned_calls: list[dict] = []
    for e in job_spec.entities:
        if e.kind == "collections":
            objective = "settle the collections balance in full, or demand written debt validation"
            lvs = collections_ids
        elif e.kind == "facility":
            objective = "remove the billing errors and settle to the benchmarked rate"
            lvs = provider_ids
        else:  # er_physician_group / radiology / anesthesia / pathology
            objective = "dispute the physician-group charges and cite the benchmarks"
            lvs = provider_ids
        planned_calls.append({"entity": e.kind, "name": e.name, "objective": objective, "levers": lvs})

    stmt = bill.statement_date
    timeline = {
        "fap_deadline": _add_days(stmt, _lever_param("501r_charity_care", "application_window_days", 240)),
        "gfe_dispute_deadline": None,           # patient is insured — GFE lever not armed
        "fdcpa_validation_deadline": None,      # no first-contact date on file yet
        "credit_report_earliest": _add_days(stmt, _lever_param("credit_bureau_under_500", "reporting_delay_days", 365)),
        "collections_referral_window_start": None,  # not modeled from statement alone
    }

    return {
        "patient_first_name": (job_spec.patient.get("legal_name") or "there").split()[0],
        "facility": {"name": bill.facility_name, "nonprofit": bool(bill.nonprofit_status)},
        "balance": balance,
        "flags": [
            {"type": f.type, "cpt": f.cpt, "dollar_impact": f.dollar_impact, "plain": _plain(f, benchmarks)}
            for f in flags
        ],
        "entities": [{"kind": e.kind, "name": e.name, "balance": e.balance} for e in job_spec.entities],
        "savings_estimate": savings_estimate,
        "levers_armed": [
            {"id": l["id"], "citation": l["citation"], "dollar_ask": l["dollar_ask"], "armed_by": l["armed_by"]}
            for l in armed_provider
        ],
        "boost_opportunities": boosts,
        "planned_calls": planned_calls,
        "timeline": timeline,
        "call_log": [],
        "next_scheduled": None,
    }
