"""Statutory / benchmarking lever pack — J's `config/levers.json` made usable.

`config/levers.json` is the frozen statute pack (owner: J): each lever carries a
verbatim `citable_string` (the exact words the agent may say), an `arming_condition`,
a `source`, and optional `parameters`. This module is the ONE place that:

  1. loads that file,
  2. interpolates its ``${token}`` placeholders from code-computed values
     (benchmark totals, flag impacts, CPT/dx codes) — the value fully replaces
     ``${token}`` (money values carry their own ``$``), and
  3. decides which levers are *armed* for a given case + route.

It is a leaf module: it imports nothing from the engine (so `dossier.py` and the
action-plan assembler can both consume it without an import cycle). Every dollar
figure it emits comes from the caller's computed totals or a DerivedFlag — never
invented here (PRD §7: code computes, the lever pack only supplies wording).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from ..config import REPO_ROOT, load_vertical

LEVERS_PATH = REPO_ROOT / "config" / "levers.json"
_TOKEN_RE = re.compile(r"\$\{(\w+)\}")


def hardship_pct_threshold(fpl_percent: float | None, brackets: dict) -> float | None:
    """MA HSN Medical Hardship: the % of countable income that qualifying medical
    expenses must exceed, by the case's FPL bracket (higher income → higher bar).
    `brackets` maps an upper FPL bound to a percent, plus an 'above' catch-all
    (config: thresholds.charity_lead.medical_hardship.min_expense_pct_of_income)."""
    if fpl_percent is None:
        return None
    for bound, pct in sorted((int(k), v) for k, v in brackets.items() if str(k).isdigit()):
        if fpl_percent <= bound:
            return pct
    return brackets.get("above")


def charity_lead_arming(
    charity_cfg: dict, fpl_percent: float | None, household_income: float | None,
    bill_amount: float | None,
) -> tuple[bool, str]:
    """Does the charity / financial-assistance lever arm? Returns (armed, reason).

    Arms when EITHER the flat FPL gate applies (fpl_percent <= max_fpl_percent) OR
    MA HSN Medical Hardship applies: no FPL ceiling, but qualifying medical expenses
    (the patient's bill) must exceed a rising %-of-income threshold for the bracket.
    Nonprofit gating is the caller's job — this decides income/expense eligibility."""
    max_fpl = charity_cfg.get("max_fpl_percent")
    if fpl_percent is not None and max_fpl is not None and fpl_percent <= max_fpl:
        return True, f"fpl_percent {fpl_percent:.0f} <= {max_fpl}"
    hardship = charity_cfg.get("medical_hardship") or {}
    if hardship.get("enabled") and bill_amount and household_income:
        pct = hardship_pct_threshold(fpl_percent, hardship.get("min_expense_pct_of_income", {}))
        if pct is not None and bill_amount >= (pct / 100.0) * household_income:
            return True, (f"MA medical hardship: bill ${bill_amount:,.0f} >= {pct:.0f}% of "
                          f"income ${household_income:,.0f}")
    return False, ""


@lru_cache
def load_levers() -> list[dict]:
    with open(LEVERS_PATH) as f:
        return json.load(f)


@lru_cache
def _by_id() -> dict[str, dict]:
    return {lv["lever_id"]: lv for lv in load_levers()}


def _money(x: float | None) -> str | None:
    return None if x is None else f"${x:,.2f}"


def interpolate(template: str, ctx: dict) -> str:
    """Fill ``${token}`` placeholders from ctx. Unknown tokens are left intact
    (so a partially-known lever still reads sensibly rather than crashing)."""
    return _TOKEN_RE.sub(lambda m: str(ctx.get(m.group(1), m.group(0))), template)


def citation(lever_id: str, ctx: dict) -> tuple[str, str]:
    """(interpolated citable_string, source) for a levers.json lever — the only
    sanctioned way to voice a statute/benchmark. Raises if the id is unknown."""
    lv = _by_id()[lever_id]
    return interpolate(lv["citable_string"], ctx), lv["source"]


# ── Interpolation context (all values code-computed upstream) ─────────────────
def build_context(flags: list, totals: dict, benchmarks: dict | None = None) -> dict:
    """Assemble the ``${token}`` values from the engine's flags + benchmark totals.

    `totals` carries the dossier's computed sums: `medicare_total`, `mrf_cash_total`,
    `mrf_negotiated_median_total`. Each error flag contributes the tokens its lever needs.
    `benchmarks` (optional) supplies human descriptions (e.g. the panel name).
    """
    benchmarks = benchmarks or {}
    ctx: dict = {
        "medicare_total": _money(totals.get("medicare_total")),
        "mrf_cash_total": _money(totals.get("mrf_cash_total")),
    }
    for f in flags:
        if f.type == "duplicate":
            ctx["cpt"] = f.cpt
            ctx["dup_dollar_impact"] = _money(f.dollar_impact)
        elif f.type == "upcode":
            ctx["billed_code"] = f.cpt
            ctx["supported_code"] = f.evidence.get("supported")
            dx = f.evidence.get("dx_codes") or []
            ctx["diagnosis"] = ", ".join(dx) if dx else "the documented diagnosis"
            ctx["upcode_dollar_impact"] = _money(f.dollar_impact)
        elif f.type == "unbundle":
            ctx["bundled_code"] = f.cpt
            # take the clean name before any editorial parenthetical
            desc = (benchmarks.get(f.cpt, {}).get("description") or "the panel")
            ctx["description"] = desc.split(" (")[0]
            ctx["components_total"] = _money(f.evidence.get("components_billed"))
            ctx["bundled_price"] = _money(f.evidence.get("bundled"))
            ctx["unbundle_dollar_impact"] = _money(f.dollar_impact)
    return ctx


# The engine emits its own lever ids (dossier.py); this maps each to the
# levers.json lever whose verbatim wording backs it, plus the ``${dollar_impact}``
# token that lever expects (error levers reuse the shared token name).
_ENGINE_TO_PACK: dict[str, str] = {
    "statutory_501r": "501r_charity_care",
    "error_duplicate": "duplicate_charge_dispute",
    "error_upcode": "upcode_dispute",
    "error_unbundle": "unbundle_dispute",
    "benchmark_anchor": "medicare_benchmark",
}
# levers.json error strings use ``${dollar_impact}``; map from the per-flag token.
_IMPACT_TOKEN = {
    "duplicate_charge_dispute": "dup_dollar_impact",
    "upcode_dispute": "upcode_dollar_impact",
    "unbundle_dispute": "unbundle_dollar_impact",
}


def citation_for_engine_lever(engine_id: str, ctx: dict) -> tuple[str, str] | None:
    """(citable_string, source) for a dossier lever id, or None if it has no
    backing entry in the pack (e.g. error_eob_mismatch — no statute, keep inline)."""
    # error levers are suffixed with the CPT (error_upcode_99285) — strip it
    base = engine_id
    for key in _ENGINE_TO_PACK:
        if engine_id == key or engine_id.startswith(key + "_"):
            base = key
            break
    pack_id = _ENGINE_TO_PACK.get(base)
    if pack_id is None:
        return None
    local = dict(ctx)
    if pack_id in _IMPACT_TOKEN:
        local["dollar_impact"] = ctx.get(_IMPACT_TOKEN[pack_id])
    return citation(pack_id, local)


# ── Arming: which levers apply to this case + route ───────────────────────────
def armed_levers(job_spec, flags: list, benchmarks: dict, route: str, totals: dict,
                 config: dict | None = None) -> list[dict]:
    """The armed lever pack for the action plan: verbatim citations + sources +
    dollar asks, all code-derived. Pragmatic per-lever predicates (no DSL) — the
    demo case arms exactly the set documented in docs/demo-shot-lists.md."""
    ctx = build_context(flags, totals, benchmarks)
    nonprofit = bool(job_spec.bill.nonprofit_status)
    fpl = job_spec.financial_profile.get("fpl_percent")
    balance = job_spec.bill.patient_balance
    income = job_spec.financial_profile.get("household_income")
    bill_amount = balance or job_spec.bill.total_billed
    charity_cfg = (config or load_vertical())["thresholds"]["charity_lead"]
    flag_types = {f.type for f in flags}
    neg_median_total = totals.get("mrf_negotiated_median_total")

    out: list[dict] = []

    def add(pack_id: str, armed_by: str, dollar_ask: float | None = None,
            flag_ctx: dict | None = None):
        lv = _by_id()[pack_id]
        # Use a per-flag context for error levers so each speaks ITS OWN flag's
        # tokens — the shared ctx holds only the last flag of each type (fix H3).
        base = flag_ctx if flag_ctx is not None else ctx
        local = dict(base)
        # error levers share the ``${dollar_impact}`` token name
        if pack_id in _IMPACT_TOKEN:
            local["dollar_impact"] = base.get(_IMPACT_TOKEN[pack_id])
        out.append({
            "id": pack_id,
            "category": lv["category"],
            "citation": interpolate(lv["citable_string"], local),
            "source": lv["source"],
            "dollar_ask": dollar_ask,
            "armed_by": armed_by,
            "parameters": lv.get("parameters", {}),
        })

    if route == "collections":
        add("fdcpa_debt_validation", "collections entity within validation window")
        add("credit_bureau_paid_removal", "paid-in-full settlement removes the mark")
        return out

    # provider route — statutory first (charity lead), then benchmark, then errors.
    # Charity arms via the flat FPL gate OR MA HSN Medical Hardship (no FPL ceiling).
    charity_armed, charity_reason = charity_lead_arming(charity_cfg, fpl, income, bill_amount)
    if nonprofit and charity_armed:
        add("501r_charity_care", f"nonprofit + {charity_reason}")
        if neg_median_total is not None and balance and balance > neg_median_total:
            add("501r_agb_limitation", "balance exceeds amounts generally billed")
    if totals.get("mrf_cash_total") and balance and balance > totals["mrf_cash_total"]:
        add("price_transparency_mrf", "balance exceeds the hospital's posted cash price")
    if totals.get("medicare_total"):
        add("medicare_benchmark", "Medicare rate published for these codes")
    for f in flags:
        f_ctx = build_context([f], totals, benchmarks)
        if f.type == "duplicate":
            add("duplicate_charge_dispute", "duplicate line item detected", f.dollar_impact, f_ctx)
        elif f.type == "upcode":
            add("upcode_dispute", "E/M level unsupported by the dx", f.dollar_impact, f_ctx)
        elif f.type == "unbundle":
            add("unbundle_dispute", "NCCI components billed unbundled", f.dollar_impact, f_ctx)
    return out
