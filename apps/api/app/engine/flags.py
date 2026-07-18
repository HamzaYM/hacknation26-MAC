"""Red-flag detection — deterministic, config-driven (PRD §7).

Every rule reads its thresholds from config/verticals/<vertical>.yaml
(`red_flags` section) and its reference prices from the benchmarks table +
data/seed/ncci_pairs.json. The LLM never computes a flag; it only explains
the ones this module emits.

Dollar-impact conventions (documented here because the answer key depends
on them — see apps/api/tests/test_flags.py for the demo arithmetic):
  duplicate     billed total of the occurrences beyond the first
  upcode        billed − counterfactual price of the records-supported code
                (counterfactual = mrf_negotiated_median, else mrf_cash, else
                band_high of the supported code's benchmark row)
  unbundle      components_total − bundled_price (from the NCCI table)
  eob_mismatch  bill.patient_balance − eob.patient_responsibility_total
  markup        billed − band_high × flag_above_band_multiple
Markup skips lines already implicated in another flag so the same dollars
are never claimed twice — and so the demo bill yields exactly its 4 seeded
flags (PRD §10.3).
"""
from __future__ import annotations

import json

from ..config import REPO_ROOT
from ..models import DerivedFlag, JobSpec, LineItem


def load_ncci_table(config: dict) -> dict:
    """NCCI bundle table, path from config (red_flags.unbundle.ncci_table)."""
    path = REPO_ROOT / config["red_flags"]["unbundle"]["ncci_table"]
    with open(path) as f:
        return json.load(f)


def detect_flags(
    job_spec: JobSpec,
    config: dict,
    benchmarks: dict[str, dict],
    ncci_table: dict | None = None,
) -> list[DerivedFlag]:
    """All red flags for a JobSpec, in stable order: duplicate → upcode →
    unbundle → eob_mismatch → markup."""
    rf = config["red_flags"]
    lines = job_spec.bill.line_items
    if ncci_table is None:
        ncci_table = load_ncci_table(config)

    flags: list[DerivedFlag] = []
    implicated_cpts: set[str] = set()  # lines already explained by a flag → markup skips

    # ── duplicate: same values on the config's match_on keys ──────────────
    groups: dict[tuple, list[LineItem]] = {}
    for li in lines:
        key = tuple(getattr(li, k) for k in rf["duplicate"]["match_on"])
        groups.setdefault(key, []).append(li)
    for key, group in sorted(groups.items(), key=lambda kv: str(kv[0])):
        if len(group) < 2:
            continue
        extra = round(sum(li.billed_amount or 0.0 for li in group[1:]), 2)
        if extra < rf["duplicate"]["min_amount"]:
            continue
        implicated_cpts.add(group[0].cpt)
        flags.append(DerivedFlag(
            type="duplicate",
            cpt=group[0].cpt,
            evidence={
                "dates": [li.date_of_service for li in group],
                "count": len(group),
                "billed_amounts": [li.billed_amount for li in group],
            },
            dollar_impact=extra,
        ))

    # ── upcode candidate: em_pairs billed code + all-low-acuity dx ────────
    em_pairs = {p["billed"]: p for p in rf["upcode"]["em_pairs"]}
    low_acuity = set(rf["upcode"].get("low_acuity_dx", []))
    for li in lines:
        pair = em_pairs.get(li.cpt)
        if not pair or not li.dx_codes or not all(dx in low_acuity for dx in li.dx_codes):
            continue
        # supported level = highest suspect code that has a benchmark row
        candidates = pair["suspect_if_supported"]
        supported = next((c for c in reversed(candidates) if c in benchmarks), candidates[-1])
        row = benchmarks.get(supported)
        counterfactual = None
        basis = None
        if row:
            for basis in ("mrf_negotiated_median", "mrf_cash", "band_high"):
                if row.get(basis) is not None:
                    counterfactual = row[basis]
                    break
        impact = round((li.billed_amount or 0.0) - counterfactual, 2) if counterfactual else 0.0
        implicated_cpts.add(li.cpt)
        flags.append(DerivedFlag(
            type="upcode",
            cpt=li.cpt,
            evidence={
                "supported": supported,
                "dx_codes": li.dx_codes,
                "billed_amount": li.billed_amount,
                "supported_price": counterfactual,
                "supported_price_basis": basis,
            },
            dollar_impact=impact,
        ))

    # ── unbundle: NCCI components present instead of the bundled code ─────
    for bundle in ncci_table.get("bundles", []):
        components = set(bundle["component_codes"])
        min_components = bundle.get("min_components", 10)
        by_date: dict[str | None, list[LineItem]] = {}
        for li in lines:
            if li.cpt in components:
                by_date.setdefault(li.date_of_service, []).append(li)
        for date, comps in sorted(by_date.items(), key=lambda kv: str(kv[0])):
            if len(comps) < min_components:
                continue
            if any(li.cpt == bundle["bundled_code"] and li.date_of_service == date for li in lines):
                continue  # bundled code itself billed → not unbundled
            components_billed = round(sum(li.billed_amount or 0.0 for li in comps), 2)
            implicated_cpts |= {li.cpt for li in comps} | {bundle["bundled_code"]}
            flags.append(DerivedFlag(
                type="unbundle",
                cpt=bundle["bundled_code"],
                evidence={
                    "components_billed": components_billed,
                    "bundled": bundle["bundled_price"],
                    "component_count": len(comps),
                    "date": date,
                },
                dollar_impact=round(components_billed - bundle["bundled_price"], 2),
            ))

    # ── eob_mismatch: balance vs EOB patient responsibility ───────────────
    balance = job_spec.bill.patient_balance
    eob_total = job_spec.eob.patient_responsibility_total
    if balance is not None and eob_total is not None:
        diff = round(balance - eob_total, 2)
        if diff > rf["eob_mismatch"]["tolerance_usd"]:
            flags.append(DerivedFlag(
                type="eob_mismatch",
                cpt=None,
                evidence={"bill": balance, "eob": eob_total},
                dollar_impact=diff,
            ))

    # ── markup: billed above the fair band's top (unflagged lines only) ───
    multiple = rf["markup"]["flag_above_band_multiple"]
    for li in lines:
        row = benchmarks.get(li.cpt)
        if row is None or li.cpt in implicated_cpts or li.billed_amount is None:
            continue
        threshold = round(row["band_high"] * multiple, 2)
        if li.billed_amount > threshold:
            flags.append(DerivedFlag(
                type="markup",
                cpt=li.cpt,
                evidence={"billed": li.billed_amount, "band_high": row["band_high"], "threshold": threshold},
                dollar_impact=round(li.billed_amount - threshold, 2),
            ))

    return flags
