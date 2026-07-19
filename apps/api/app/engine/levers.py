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

from ..config import REPO_ROOT

LEVERS_PATH = REPO_ROOT / "config" / "levers.json"
_TOKEN_RE = re.compile(r"\$\{(\w+)\}")


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
def armed_levers(job_spec, flags: list, benchmarks: dict, route: str, totals: dict) -> list[dict]:
    """The armed lever pack for the action plan: verbatim citations + sources +
    dollar asks, all code-derived. Pragmatic per-lever predicates (no DSL) — the
    demo case arms exactly the set documented in docs/demo-shot-lists.md."""
    ctx = build_context(flags, totals, benchmarks)
    nonprofit = bool(job_spec.bill.nonprofit_status)
    fpl = job_spec.financial_profile.get("fpl_percent")
    balance = job_spec.bill.patient_balance
    flag_types = {f.type for f in flags}
    neg_median_total = totals.get("mrf_negotiated_median_total")

    out: list[dict] = []

    def add(pack_id: str, armed_by: str, dollar_ask: float | None = None):
        lv = _by_id()[pack_id]
        local = dict(ctx)
        # error levers share the ``${dollar_impact}`` token name
        if pack_id in _IMPACT_TOKEN:
            local["dollar_impact"] = ctx.get(_IMPACT_TOKEN[pack_id])
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

    # provider route — statutory first (charity lead), then benchmark, then errors
    if nonprofit and fpl is not None and fpl <= 400:
        add("501r_charity_care", f"nonprofit + {fpl:.0f}% FPL")
        if neg_median_total is not None and balance and balance > neg_median_total:
            add("501r_agb_limitation", "balance exceeds amounts generally billed")
    if totals.get("mrf_cash_total") and balance and balance > totals["mrf_cash_total"]:
        add("price_transparency_mrf", "balance exceeds the hospital's posted cash price")
    if totals.get("medicare_total"):
        add("medicare_benchmark", "Medicare rate published for these codes")
    for f in flags:
        if f.type == "duplicate":
            add("duplicate_charge_dispute", "duplicate line item detected", f.dollar_impact)
        elif f.type == "upcode":
            add("upcode_dispute", "E/M level unsupported by the dx", f.dollar_impact)
        elif f.type == "unbundle":
            add("unbundle_dispute", "NCCI components billed unbundled", f.dollar_impact)
    return out
