"""Report builder — deterministic ranking + per-CPT lines + recommendation.

All pure functions over outcome dicts / the JobSpec / benchmarks so tests can
cover them without a DB. No LLM anywhere: the recommendation string is
assembled from data.

Ranking (frozen contract): primary = achieved amount as % of the fair band
(lower is better) for monetary outcomes; non-monetary states ordered
charity_app_initiated > callback > documented_decline.
"""
from __future__ import annotations

from ..models import DerivedFlag, JobSpec
from .dossier import corrected_cpt_set

_NON_MONETARY_ORDER = {
    "charity_app_initiated": 0,
    "payment_plan": 1,
    "callback": 2,
    "documented_decline": 3,
}


def fair_total(job_spec: JobSpec, flags: list[DerivedFlag], benchmarks: dict[str, dict]) -> float:
    """Fair-band total (band_high) over the corrected CPT set."""
    cpts = corrected_cpt_set(job_spec, flags, benchmarks)
    return round(sum(benchmarks[c]["band_high"] for c in cpts), 2)


def rank_outcomes(outcomes: list[dict], fair: float) -> list[dict]:
    monetary, non_monetary = [], []
    for o in outcomes:
        o = dict(o)
        if o.get("final_amount") is not None:
            o["achieved_pct_of_fair"] = round(100.0 * float(o["final_amount"]) / fair, 1) if fair else None
            monetary.append(o)
        else:
            non_monetary.append(o)
    monetary.sort(key=lambda o: (o["achieved_pct_of_fair"] is None, o["achieved_pct_of_fair"]))
    non_monetary.sort(key=lambda o: _NON_MONETARY_ORDER.get(o.get("outcome_type"), 99))
    return monetary + non_monetary


def build_lines(job_spec: JobSpec, flags: list[DerivedFlag], benchmarks: dict[str, dict],
                settlement: float | None) -> list[dict]:
    """Per-CPT billed vs fair (band_high) vs achieved. Billed amounts are mapped
    onto the corrected codes (upcode → supported level, unbundle → bundled code);
    achieved allocates the settlement proportionally to billed."""
    billed: dict[str, float] = {}
    for li in job_spec.bill.line_items:
        billed[li.cpt] = billed.get(li.cpt, 0.0) + (li.billed_amount or 0.0)
    for flag in flags:
        if flag.type == "upcode" and flag.cpt in billed:
            billed[flag.evidence["supported"]] = (
                billed.get(flag.evidence["supported"], 0.0) + billed.pop(flag.cpt)
            )
        elif flag.type == "unbundle" and flag.cpt:
            billed[flag.cpt] = billed.get(flag.cpt, 0.0) + float(
                flag.evidence.get("components_billed", 0.0)
            )

    lines = [
        {"cpt": cpt, "billed": round(amount, 2), "fair": float(benchmarks[cpt]["band_high"])}
        for cpt, amount in billed.items()
        if cpt in benchmarks and amount > 0
    ]
    lines.sort(key=lambda l: -l["billed"])
    shown_total = sum(l["billed"] for l in lines)
    for line in lines:
        line["achieved"] = (
            round(settlement * line["billed"] / shown_total, 2)
            if settlement is not None and shown_total else None
        )
    return lines


def _entity(outcome: dict) -> str:
    return outcome.get("target_entity") or "the provider"


def build_recommendation(ranked: list[dict]) -> str:
    if not ranked:
        return ("No completed calls yet — launch the negotiation calls to generate "
                "outcomes for this case.")
    # One sentence per ENTITY (best-ranked outcome wins). Without this the
    # recommendation degrades every demo re-run (probe finding: 12+ accumulated
    # outcomes rendered a ~2,000-char wall of repeated sentences).
    seen_entities: set[str] = set()
    deduped: list[dict] = []
    for o in ranked:
        key = o.get("target_entity") or o.get("entity") or "?"
        if key in seen_entities:
            continue
        seen_entities.add(key)
        deduped.append(o)
    parts: list[str] = []
    for o in deduped:
        otype = o.get("outcome_type")
        if o.get("final_amount") is not None:
            final, orig = float(o["final_amount"]), o.get("original_amount")
            msg = f"Accept the {_entity(o)} settlement of ${final:,.0f}"
            if orig:
                pct = o.get("reduction_pct") or round(100 * (1 - final / float(orig)), 1)
                msg += f" (down {pct:.0f}% from ${float(orig):,.0f})"
            if o.get("reference_number"):
                msg += f", reference {o['reference_number']}"
            parts.append(msg + ".")
        elif otype == "charity_app_initiated":
            msg = f"Complete the financial-assistance application with {_entity(o)}"
            if o.get("reference_number"):
                msg += f" (reference {o['reference_number']})"
            parts.append(msg + ".")
        elif otype == "payment_plan":
            parts.append(f"Review the payment plan offered by {_entity(o)}.")
        elif otype == "callback":
            parts.append(f"Take the scheduled callback with {_entity(o)}.")
        elif otype == "documented_decline":
            parts.append(f"{_entity(o)} declined — the refusal is documented; "
                         "schedule a callback with a supervisor.")
    return " ".join(parts)
