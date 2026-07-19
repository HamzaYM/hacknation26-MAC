"""Benchmark-report builder — the anchor set for every bill line (stage 6-7).

Produces a BenchmarkReport (contracts/anchor_set.schema.json) for a JobSpec by
querying the lookup layer (engine/lookup.py). Every anchor carries full
provenance (source, source_url, formula, confidence, label); every derived
number (medicare_multiple, fair_band, rand_flag, excess_above_band) is plain
arithmetic over config multiples. No LLM, no invented numbers — `None` from the
lookup becomes an honest coverage status, never a guessed price.

The report exposes what dossier.py historically computed internally but never
surfaced (audit engine.md, dossier.py:70-71): per-line and total Medicare
multiples, the fair band, and the RAND-ceiling flag.
"""
from __future__ import annotations

from ..models import JobSpec
from .flags import infer_code_type

_RAND_SOURCE_URL = "https://www.rand.org/pubs/research_reports/RRA1144-1.html"
_MEDICARE_SOURCE_URL = "https://www.cms.gov/medicare/payment/fee-schedules"


def _component_for_entity(billing_entity: str | None) -> str:
    # Casefold/strip — billing_entity is an unconstrained Optional[str]; an
    # extracted "Facility" must still select the facility component, not fall to
    # the global fallback and mis-price the line (M8, mirrors flags.py).
    return {"facility": "facility", "professional": "professional"}.get(
        (billing_entity or "").strip().lower(), "global")


def _line_anchors(lookup, hospital: str, code: str, billing_entity: str | None,
                  payer_name: str | None, plan_name: str | None,
                  units: float, rand_norm_multiple: float) -> tuple[list[dict], float | None]:
    """Every applicable anchor for a line + the per-line Medicare value (rate×units)."""
    anchors: list[dict] = []
    medicare_line: float | None = None

    # Medicare — professional/facility component per billing entity, global fallback.
    wanted = _component_for_entity(billing_entity)
    mrate = lookup.medicare_rate(code, wanted) or lookup.medicare_rate(code, "global")
    if mrate is not None:
        medicare_line = round(mrate.value * units, 2)
        anchors.append({
            "method": "medicare", "value": round(mrate.value, 2),
            "component": mrate.component,
            "formula": mrate.formula or "(wRVU*wGPCI + peRVU*peGPCI + mpRVU*mpGPCI) * CF",
            "source": f"medicare_rates[{code}/{mrate.component}] {mrate.version}",
            "source_url": mrate.source_url or _MEDICARE_SOURCE_URL,
            "confidence": "estimated" if "fixture" in mrate.version or "synthetic" in mrate.version else "high",
            "label": f"Medicare {mrate.component} rate",
        })
        # RAND-norm estimate — ALWAYS labeled as an estimate, never a real quote.
        anchors.append({
            "method": "rand_norm_estimate", "value": round(mrate.value * rand_norm_multiple, 2),
            "component": None,
            "formula": f"Medicare x {rand_norm_multiple} (RAND commercial norm)",
            "source": f"derived: medicare {mrate.component} x {rand_norm_multiple}",
            "source_url": _RAND_SOURCE_URL,
            "confidence": "estimated",
            "label": "estimated (RAND norm)",
        })

    # Plan-specific negotiated rate (only when we know the payer).
    if payer_name:
        prate = lookup.plan_rate(hospital, code, payer_name, plan_name)
        if prate is not None:
            anchors.append({
                "method": "plan_rate", "value": round(prate, 2), "component": None,
                "formula": None,
                "source": f"chargemaster_charges[{hospital}/{code}] payer={payer_name}"
                          + (f" plan={plan_name}" if plan_name else ""),
                "source_url": None, "confidence": "high",
                "label": f"{payer_name} negotiated rate",
            })

    # Cross-payer band over commercial negotiated rows.
    stats = lookup.cross_payer_stats(hospital, code)
    if stats:
        anchors.append({
            "method": "cross_payer_band", "value": round(stats["median"], 2), "component": None,
            "band": {k: stats[k] for k in ("p25", "median", "p75", "min", "max", "n_payers", "n_rows")
                     if k in stats},
            "formula": "p25/median/p75 of commercial negotiated_dollar (outlier-trimmed)",
            "source": f"chargemaster_charges[{hospital}/{code}] commercial rows",
            "source_url": None, "confidence": "high",
            "label": f"cross-payer median ({stats.get('n_payers', 0)} payers)",
        })

    cash = lookup.cash_price(hospital, code)
    if cash is not None:
        anchors.append({
            "method": "cash_price", "value": round(cash, 2), "component": None,
            "formula": None, "source": f"chargemaster_charges[{hospital}/{code}] cash",
            "source_url": None, "confidence": "high", "label": "hospital cash price",
        })

    gross = lookup.gross_charge(hospital, code)
    if gross is not None:
        anchors.append({
            "method": "gross_charge", "value": round(gross, 2), "component": None,
            "formula": None, "source": f"chargemaster_charges[{hospital}/{code}] gross",
            "source_url": None, "confidence": "high", "label": "chargemaster list price",
        })

    return anchors, medicare_line


def _coverage(lookup, hospital: str, code: str, billing_entity: str | None,
              medicare_line: float | None, stats: dict | None, std_types: set) -> str:
    in_cm = lookup.code_in_chargemaster(hospital, code)
    if in_cm:
        n_payers = (stats or {}).get("n_payers", 0)
        return "full" if n_payers >= 3 else "thin"
    if billing_entity == "professional":
        return "professional_excluded"
    if billing_entity == "facility" and infer_code_type(code) in std_types:
        return "absent_from_chargemaster"
    if medicare_line is None:
        return "no_medicare"
    return "thin"


def build_benchmark_report(job_spec: JobSpec, lookup, config: dict) -> dict:
    """Build the BenchmarkReport (contracts/anchor_set.schema.json) for a case."""
    bench = config["benchmark"]
    band_low_m = bench["band_low_multiple"]
    band_high_m = bench["band_high_multiple"]
    rand_norm_multiple = bench.get("rand_norm_multiple", 2.54)
    rand_ceiling = bench.get("rand_ceiling_multiple", 2.54)
    target_low_m = bench["self_pay_target_multiple_low"]
    target_high_m = bench["self_pay_target_multiple_high"]
    std_types = set(config["red_flags"].get("absent_from_chargemaster", {})
                    .get("standard_code_types", ["CPT", "HCPCS", "DRG", "MS-DRG"]))

    # Normalize the hospital key at the lookup boundary (strip statement-header
    # whitespace), consistent with flags.py and the lookup layer's payer/plan
    # normalization — trivial extraction noise must not blank every anchor (L3).
    hospital = (job_spec.bill.facility_name or "").strip()
    ins = job_spec.insurance or {}
    payer_name = ins.get("payer_name")
    plan_name = ins.get("plan_type") or ins.get("plan_name")

    lines_out: list[dict] = []
    line_medicare: list[float | None] = []  # parallel to lines_out; per-line Medicare $ (L1)
    medicare_version = f"lookup:{lookup.version()}"
    for li in job_spec.bill.line_items:
        code = li.cpt
        units = float(li.units if li.units is not None else 1)
        billed = round(float(li.billed_amount), 2) if li.billed_amount is not None else 0.0
        billing_entity = li.billing_entity or "unknown"

        anchors, medicare_line = _line_anchors(
            lookup, hospital, code, li.billing_entity, payer_name, plan_name, units, rand_norm_multiple)
        stats = next((a.get("band") for a in anchors if a["method"] == "cross_payer_band"), None)
        med_anchor = next((a for a in anchors if a["method"] == "medicare"), None)
        if med_anchor is not None:
            medicare_version = med_anchor["source"]  # provenance string of the Medicare rate used

        # A GENUINELY RESOLVED Medicare rate of $0.00 (CMS OPPS packaged / zero-RVU
        # codes) is real data, not missing data — use `is not None`, not truthiness,
        # so a $0 rate still yields a fair band, rand_flag and excess rather than
        # collapsing into the no-Medicare state (fix L2). medicare_multiple is left
        # None only for the genuine divide-by-zero ($0 rate) case.
        has_medicare = medicare_line is not None
        medicare_multiple = round(billed / medicare_line, 2) if (has_medicare and medicare_line) else None
        fair_band = None
        rand_flag = False
        excess = 0.0
        if has_medicare:
            fair_band = {
                "low": round(band_low_m * medicare_line, 2),
                "high": round(band_high_m * medicare_line, 2),
                "basis": "Medicare x config band multiples",
                "low_multiple": band_low_m, "high_multiple": band_high_m,
            }
            rand_flag = billed > round(rand_ceiling * medicare_line, 2)
            excess = round(max(0.0, billed - fair_band["high"]), 2)

        coverage = _coverage(lookup, hospital, code, li.billing_entity, medicare_line, stats, std_types)

        lines_out.append({
            "code": code, "code_type": infer_code_type(code),
            "description": li.description, "billing_entity": billing_entity,
            "units": units, "billed": billed, "anchors": anchors,
            "medicare_multiple": medicare_multiple, "fair_band": fair_band,
            "rand_flag": rand_flag, "excess_above_band": excess, "coverage": coverage,
        })
        # per-line Medicare dollars (rate×units) carried out-of-band for exact
        # totals (L1) — kept off the anchor-set surface so it never leaks into the
        # persisted report / answer keys.
        line_medicare.append(medicare_line)

    billed_total = round(sum(l["billed"] for l in lines_out), 2)
    med_lines_medicare = [m for l, m in zip(lines_out, line_medicare) if l["fair_band"] is not None]
    med_lines = [l for l in lines_out if l["fair_band"] is not None]
    # Sum the per-line Medicare dollars the engine already computed — do NOT invert
    # a rounded fair_band["low"], which introduces per-line drift that can flip the
    # reported cents of the total and every ask derived from it (fix L1).
    medicare_total = round(sum(med_lines_medicare), 2) if med_lines_medicare else None
    fair_low = round(sum(l["fair_band"]["low"] for l in med_lines), 2)
    fair_high = round(sum(l["fair_band"]["high"] for l in med_lines), 2)
    # Excess = the sum of each line's OWN excess_above_band — never the billed total
    # minus a fair_high that omits un-benchmarked lines, which would smuggle an
    # un-benchmarked line's full billed amount in as "excess above band" and break
    # the module's "None never becomes a guessed price" promise at the totals level
    # (fix H2).
    excess_total = round(sum(l["excess_above_band"] for l in lines_out), 2)

    totals = {
        "billed": billed_total,
        "medicare": medicare_total,
        "medicare_multiple": round(billed_total / medicare_total, 2) if medicare_total else None,
        "fair_band_low": fair_low, "fair_band_high": fair_high,
        "excess_above_band": excess_total,
        "ask_anchor": round(target_low_m * medicare_total, 2) if medicare_total else 0.0,
        "ask_target": round(target_high_m * medicare_total, 2) if medicare_total else 0.0,
        "floor": medicare_total or 0.0,  # Medicare is the hard price floor
    }

    return {
        "case_id": job_spec.case_id,
        "hospital": hospital,
        "payer_name": payer_name,
        "plan_name": plan_name,
        "lines": lines_out,
        "totals": totals,
        "data_version": {
            "chargemaster": lookup.version(),
            "medicare": medicare_version,
            "config": config.get("vertical", "medical_bills"),
        },
    }
