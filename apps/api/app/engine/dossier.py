"""StrategyDossier builder — route + armed levers + anchor/target/floor (PRD §8).

All numbers are code-computed from the JobSpec, the benchmarks table, and
config/verticals/<vertical>.yaml. The dossier is the ONLY source of numbers
the negotiator agent may speak (honesty policy, PRD §8.5).

Money math (asserted against data/seed/demo_answer_key.json in tests):
  corrected CPT set = bill lines, deduped, with upcoded codes replaced by
                      their records-supported level and unbundled components
                      replaced by the bundled code (benchmark-covered codes only)
  anchor = self_pay_target_multiple_low  × Medicare total of that set
  target = min(MRF cash total, self_pay_target_multiple_high × Medicare total)
  floor  = financial_profile.lump_sum_available — the most the patient can pay;
           the state machine rejects any offer above it, and settling above
           target raises an escalation flag (see state_machine.py)

Levers are emitted in ladder order (config ladder.provider): a protected NSA
statute (armed FIRST when an nsa flag is present — cite, don't negotiate) →
statutory (financial_assistance_screen rung) → error disputes (line_item_disputes
rung, one lever per red flag) → benchmark_anchor. Only armed levers are listed.
"""
from __future__ import annotations

from . import levers
from ..models import DerivedFlag, Entity, JobSpec, Lever, StrategyDossier

ERROR_FLAG_TYPES = ("duplicate", "upcode", "unbundle", "phantom", "eob_mismatch")


def corrected_cpt_set(job_spec: JobSpec, flags: list[DerivedFlag], benchmarks: dict[str, dict]) -> set[str]:
    """The codes the bill SHOULD contain, per the red flags — the basis for
    all benchmark totals. Restricted to codes with a benchmark row."""
    cpts = {li.cpt for li in job_spec.bill.line_items}
    for flag in flags:
        if flag.type == "upcode":
            cpts.discard(flag.cpt)
            cpts.add(flag.evidence["supported"])
        elif flag.type == "unbundle":
            cpts.add(flag.cpt)  # components carry no benchmark rows → filtered below
    return {c for c in cpts if c in benchmarks}


def _cite(row: dict) -> str:
    parts = [f"CPT {row['cpt']} ({row.get('description', '')}): Medicare ${row['medicare_rate']:.2f}"]
    if row.get("mrf_cash") is not None:
        parts.append(f"MRF cash ${row['mrf_cash']:.2f}")
    if row.get("mrf_negotiated_median") is not None:
        parts.append(f"MRF negotiated median ${row['mrf_negotiated_median']:.2f}")
    parts.append(f"fair band ${row['band_low']:.2f}–${row['band_high']:.2f}")
    if row.get("source_url"):
        parts.append(f"source: {row['source_url']}")
    return " · ".join(parts)


def build_dossier(
    job_spec: JobSpec,
    flags: list[DerivedFlag],
    benchmarks: dict[str, dict],
    config: dict,
    entity: Entity | None = None,
) -> StrategyDossier:
    entity = entity or job_spec.entities[0]
    route = "collections" if entity.kind == "collections" else "provider"

    cpts = corrected_cpt_set(job_spec, flags, benchmarks)
    medicare_total = round(sum(benchmarks[c]["medicare_rate"] for c in cpts), 2)
    mrf_cash_total = round(
        sum(benchmarks[c]["mrf_cash"] for c in cpts if benchmarks[c].get("mrf_cash") is not None), 2
    )

    bench_cfg = config["benchmark"]
    anchor = round(bench_cfg["self_pay_target_multiple_low"] * medicare_total, 2)
    high_ask = round(bench_cfg["self_pay_target_multiple_high"] * medicare_total, 2)
    target = min(mrf_cash_total, high_ask) if mrf_cash_total else high_ask
    floor = job_spec.financial_profile.get("lump_sum_available")
    if floor is None:
        floor = target  # conservative fallback: never offer above target

    # Citation wording comes verbatim from J's statute pack (config/levers.json),
    # interpolated with the code-computed totals + flag impacts (engine/levers.py).
    # The engine owns the numbers; the pack owns the words (PRD §7).
    lever_ctx = levers.build_context(
        flags, {"medicare_total": medicare_total, "mrf_cash_total": mrf_cash_total}, benchmarks
    )

    def _pack_cite(engine_id: str, fallback: str | None = None) -> str | None:
        cited = levers.citation_for_engine_lever(engine_id, lever_ctx)
        return cited[0] if cited else fallback

    levers_list: list[Lever] = []

    # 0) NSA gate — a protected out-of-network emergency/ancillary balance is
    #    CITED, not negotiated (config thresholds.nsa_do_not_negotiate). There is
    #    no nsa_dispute rung in the ladder, so we keep the route but arm the NSA
    #    statute lever FIRST, with the verbatim citation from config/levers.json.
    nsa_flag = next((f for f in flags if f.type == "nsa"), None)
    if nsa_flag is not None:
        try:
            nsa_cite = levers.citation("nsa_emergency_balance_billing_ban", lever_ctx)[0]
        except KeyError:
            nsa_cite = None  # pack missing the lever → arm without a citation
        levers_list.append(Lever(
            id="statutory_nsa",
            armed=True,
            armed_by=f"derived_flag:nsa (protected OON balance ${nsa_flag.dollar_impact:,.2f})",
            citation=nsa_cite,
            dollar_ask=nsa_flag.dollar_impact,
        ))

    # 1) statutory — financial_assistance_screen rung (charity care FIRST)
    charity = config["thresholds"]["charity_lead"]
    fpl = job_spec.financial_profile.get("fpl_percent")
    if job_spec.bill.nonprofit_status and fpl is not None and fpl <= charity["max_fpl_percent"]:
        levers_list.append(Lever(
            id="statutory_501r",
            armed=True,
            armed_by=f"nonprofit_status + fpl_percent {fpl:.0f} <= {charity['max_fpl_percent']}",
            citation=_pack_cite("statutory_501r"),
            dollar_ask=None,
        ))

    # 2) error disputes — line_item_disputes rung, one lever per red flag
    for flag in flags:
        if flag.type not in ERROR_FLAG_TYPES:
            continue
        lever_id = f"error_{flag.type}" + (f"_{flag.cpt}" if flag.cpt else "")
        row = benchmarks.get(flag.evidence.get("supported") or flag.cpt or "")
        # eob_mismatch has no statute in the pack → fall back to the per-CPT cite
        levers_list.append(Lever(
            id=lever_id,
            armed=True,
            armed_by=f"derived_flag:{flag.type}",
            citation=_pack_cite(lever_id, fallback=_cite(row) if row else None),
            dollar_ask=flag.dollar_impact,
        ))

    # 3) benchmark anchor — Medicare + the hospital's own posted cash price,
    #    both voiced verbatim from the pack (medicare_benchmark + price_transparency_mrf)
    if cpts:
        anchor_cite = _pack_cite("benchmark_anchor")
        cash_cite = None
        if mrf_cash_total:
            cash_cite = levers.citation("price_transparency_mrf", lever_ctx)[0]
        levers_list.append(Lever(
            id="benchmark_anchor",
            armed=True,
            armed_by="benchmarks",
            citation=" ".join(c for c in (anchor_cite, cash_cite) if c) or None,
            dollar_ask=anchor,
        ))

    return StrategyDossier(
        case_id=job_spec.case_id,
        target_entity=entity.name,
        route=route,
        levers=levers_list,
        anchor=anchor,
        target=target,
        floor=floor,
        citations=[_cite(benchmarks[c]) for c in sorted(cpts)],
    )
