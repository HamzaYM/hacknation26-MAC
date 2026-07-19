"""Red-flag detection — deterministic, config-driven (PRD §7, generalized-pipeline §2).

Every rule reads its thresholds from config/verticals/<vertical>.yaml
(`red_flags` section) and its reference prices from the benchmarks table +
data/seed/ncci_pairs.json. The LLM never computes a flag; it only explains
the ones this module emits.

Detectors (stable order): duplicate → upcode → unbundle (panel bundles + NCCI
PTP pairs) → phantom → nsa → denial → units_error →
absent_from_chargemaster → eob_mismatch → markup.

The bill<->EOB detectors (phantom, denial, units_error, line-level
eob_mismatch) consume engine.reconcile output; absent_from_chargemaster
consumes the lookup layer. Both are optional inputs — when omitted, those
detectors stay dormant, so the fixture/offline path behaves exactly as before.

Dollar-impact conventions (documented here because the answer key depends
on them — see apps/api/tests/test_flags.py for the demo arithmetic):
  duplicate     billed total of the occurrences beyond the first
  upcode        billed − counterfactual price of the records-supported code
                (counterfactual = mrf_negotiated_median, else mrf_cash, else
                band_high of the supported code's benchmark row)
  unbundle      components_total − bundled_price (panels), or the billed amount
                of the column-2 code (NCCI PTP pairs)
  phantom       billed amount of the bill line with no EOB counterpart
  nsa           bill.patient_balance − eob.patient_responsibility_total, for a
                protected out-of-network emergency/ancillary provider (No
                Surprises Act — cited, never negotiated). Fired by EITHER the
                marker-based signal (#67: OON line marker + ancillary entity) OR
                the generalized reconciliation signal (WS2: in-network/emergency
                balance billing); deduped to a single "nsa" flag.
  denial        patient_responsibility (else billed) of a $0-paid EOB line
  units_error   per-unit price × excess units over the allowed/plausible ceiling
  absent_from_chargemaster  billed amount of the un-posted facility line
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
from .reconcile import reconcile


def load_ncci_table(config: dict) -> dict:
    """NCCI bundle table, path from config (red_flags.unbundle.ncci_table)."""
    path = REPO_ROOT / config["red_flags"]["unbundle"]["ncci_table"]
    with open(path) as f:
        return json.load(f)


def infer_code_type(code: str | None) -> str:
    """Best-effort code-type inference from the code's shape. CPT = 5 digits;
    HCPCS = letter + 4 digits (e.g. J7030); MS-DRG = 3 digits; else internal/local
    (CDM). Used to gate absent_from_chargemaster to *standard* codes only."""
    if not code:
        return "LOCAL"
    c = code.strip().upper()
    if len(c) == 5 and c.isdigit():
        return "CPT"
    if len(c) == 5 and c[0].isalpha() and c[1:].isdigit():
        return "HCPCS"
    if len(c) == 3 and c.isdigit():
        return "MS-DRG"
    return "LOCAL"


def _eob_present(eob) -> bool:
    """Did the payer adjudicate this claim? True when there are EOB line items or
    a patient-responsibility total. Distinguishes insured from self-pay so the
    bill<->EOB detectors don't fire on self-pay bills."""
    if eob is None:
        return False
    return bool(getattr(eob, "line_items", None)) or getattr(eob, "patient_responsibility_total", None) is not None


def detect_flags(
    job_spec: JobSpec,
    config: dict,
    benchmarks: dict[str, dict],
    ncci_table: dict | None = None,
    *,
    lookup=None,
    reconciliation: dict | None = None,
) -> list[DerivedFlag]:
    """All red flags for a JobSpec, in stable detector order: duplicate → upcode
    → unbundle (panels + NCCI PTP) → phantom → nsa → denial → units_error →
    absent_from_chargemaster → eob_mismatch → markup.

    `lookup` (a BenchmarkLookup) enables absent_from_chargemaster; when None the
    detector is skipped. `reconciliation` may be supplied to reuse a prior
    engine.reconcile pass; when None it is computed from the bill+EOB here.
    """
    rf = config["red_flags"]
    lines = job_spec.bill.line_items
    if ncci_table is None:
        ncci_table = load_ncci_table(config)

    eob_present = _eob_present(job_spec.eob)
    if reconciliation is None:
        reconciliation = reconcile(job_spec.bill, job_spec.eob if eob_present else None)

    flags: list[DerivedFlag] = []
    # Lines already explained by a flag → later detectors (markup, PTP, phantom,
    # units, absent) skip them so the same dollars are never claimed twice. Keyed
    # by LINE IDENTITY (cpt, date_of_service) — NOT bare CPT — so an unrelated
    # occurrence of the same code on a *different* date stays independently
    # detectable (fix H1). Helper keeps the tuple construction in one place.
    implicated: set[tuple] = set()

    def _key(code, date):
        return (code, date)

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
        implicated.add(_key(group[0].cpt, group[0].date_of_service))
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
    # Normalize the low-acuity dx set + each line's dx codes (strip/upper) before
    # membership — the same normalization infer_code_type/the SQLite layer apply —
    # so an extraction artifact like 'J06.9 ' doesn't defeat the detector (M9).
    low_acuity = {str(dx).strip().upper() for dx in rf["upcode"].get("low_acuity_dx", [])}
    for li in lines:
        pair = em_pairs.get(li.cpt)
        if not pair or not li.dx_codes or not all(
                str(dx).strip().upper() in low_acuity for dx in li.dx_codes):
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
        # No defensible counterfactual price → we cannot substantiate a dollar
        # overcharge, so do NOT emit a misleading $0-impact upcode "finding" (H5).
        if counterfactual is None:
            continue
        impact = round((li.billed_amount or 0.0) - counterfactual, 2)
        implicated.add(_key(li.cpt, li.date_of_service))
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
    # Subsumption: if a comprehensive bundle fires (e.g. CMP 80053), skip
    # subset bundles (e.g. BMP 80048) for the same date.  Track fired
    # component sets per date to enforce this.
    # (Subsumption + PTP-edit table both incorporated from origin/database-work,
    #  data/seed/ncci_pairs.json — see commit message.)
    fired_components_by_date: dict[str | None, list[set[str]]] = {}
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
            # Subsumption check: skip if this bundle's components are a
            # subset of (or equal to) an already-fired bundle on this date.
            matched_cpts = {li.cpt for li in comps}
            if any(matched_cpts <= fired for fired in fired_components_by_date.get(date, [])):
                continue
            components_billed = round(sum(li.billed_amount or 0.0 for li in comps), 2)
            implicated |= {_key(li.cpt, date) for li in comps} | {_key(bundle["bundled_code"], date)}
            fired_components_by_date.setdefault(date, []).append(matched_cpts)
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

    # ── unbundle (NCCI PTP): a column-2 code billed alongside its column-1
    #    code on the same date; the column-2 code should have been denied.
    #    modifier_indicator 0 = never unbundlable (higher severity); 1 = a
    #    modifier could legitimately unbundle (low severity, note it).
    by_date_cpt: dict[str | None, dict[str, list[LineItem]]] = {}
    for li in lines:
        by_date_cpt.setdefault(li.date_of_service, {}).setdefault(li.cpt, []).append(li)
    for group in ncci_table.get("ptp_edits", []):
        for pair in group.get("pairs", []):
            c1, c2 = pair["column_1"], pair["column_2"]
            for date, cpt_map in sorted(by_date_cpt.items(), key=lambda kv: str(kv[0])):
                if c1 not in cpt_map or c2 not in cpt_map:
                    continue
                # The PTP flag claims the column-2 code's dollars ON THIS DATE, so
                # skip only when THOSE dollars are already claimed (e.g. a panel
                # bundle subsumed c2 on this date). Do NOT skip merely because c1
                # was implicated by an unrelated flag (a same-day duplicate of c1,
                # or c1 on another date) — that would swallow an independent
                # column-2 violation (fix H1 / cross-date + duplicate suppression).
                if _key(c2, date) in implicated:
                    continue
                c2_lines = cpt_map[c2]
                impact = round(sum(li.billed_amount or 0.0 for li in c2_lines), 2)
                mod = pair.get("modifier_indicator", 0)
                implicated |= {_key(c1, date), _key(c2, date)}
                flags.append(DerivedFlag(
                    type="unbundle",
                    cpt=c2,
                    evidence={
                        "ptp_pair": [c1, c2],
                        "column_1": c1,
                        "column_2": c2,
                        "modifier_indicator": mod,
                        "note": pair.get("note"),
                        "date": date,
                        "severity": "low" if mod == 1 else "medium",
                    },
                    dollar_impact=impact,
                ))

    # ── phantom: a bill line with no EOB counterpart, when the EOB otherwise
    #    covers that service date (the declared-but-never-emitted type). ─────
    if eob_present:
        pf = rf.get("phantom", {})
        min_amt = pf.get("min_amount", 0)
        require_cov = pf.get("require_eob_date_coverage", True)
        for row in reconciliation["bill_only"]:
            code = row["code"]
            if _key(code, row.get("date")) in implicated:
                continue
            billed = row.get("billed") or 0.0
            if billed < min_amt:
                continue
            if require_cov and not row.get("eob_covers_date"):
                continue
            implicated.add(_key(code, row.get("date")))
            flags.append(DerivedFlag(
                type="phantom",
                cpt=code,
                evidence={
                    "date": row.get("date"),
                    "billed": billed,
                    "reason": "billed line has no matching EOB line on a date the EOB adjudicated",
                },
                dollar_impact=round(billed, 2),
            ))

    # ── nsa: No Surprises Act balance billing — UNIFIED detector (integration).
    #    Emits a single "nsa" flag (the type existing tests + consumers assert)
    #    from EITHER of two protection signals, deduped to one flag per case:
    #      (a) marker-based (#67): an out-of-network emergency/ancillary line
    #          (description marker) + an ancillary entity with balance > 0. The
    #          delta is CITED, not negotiated (thresholds.nsa_do_not_negotiate).
    #      (b) generalized (WS2): insurance.network_status == in_network, or an
    #          emergency claim — reconciliation-driven balance billing.
    #    Impact is identical either way: patient_balance − EOB patient-responsibility
    #    (Nina's $3,120 − $850 = $2,270). When the marker signal applies we keep
    #    #67's exact cpt + evidence so Nina's seeded answer key still matches; the
    #    marker path wins on dedupe so that behavior is byte-stable.
    nsa_cfg = rf.get("nsa", {})
    nsa_bb_cfg = rf.get("nsa_balance_billing", {})
    balance = job_spec.bill.patient_balance
    eob_resp = job_spec.eob.patient_responsibility_total

    # (a) marker-based signal (#67 semantics)
    ancillary_kinds = set(nsa_cfg.get("ancillary_kinds", []))
    markers = [m.lower() for m in nsa_cfg.get("out_of_network_markers", [])]
    oon_line = next(
        (li for li in lines
         if li.description and any(m in li.description.lower() for m in markers)),
        None,
    )
    ancillary_entities = [
        e for e in job_spec.entities
        if e.kind in ancillary_kinds and (e.balance or 0) > 0
    ]
    # This case is in the marker path's domain when BOTH an OON-marked line and an
    # ancillary provider (a provider a patient can't choose in an emergency) are
    # present — the #67 surprise-bill shape. In that domain we require a genuine
    # linkage before asserting NSA protection: an ancillary provider whose balance
    # ALONE exceeds the entire adjudicated patient responsibility is billing above
    # the in-network cost share (a real surprise balance bill). A boilerplate OON
    # disclosure on an unrelated facility line + an ancillary whose balance is a
    # fully-reconciled in-network co-insurance share does NOT qualify (fix M2).
    marker_context = oon_line is not None and bool(ancillary_entities)
    marker_protected = marker_context and eob_resp is not None and any(
        (e.balance or 0) > eob_resp for e in ancillary_entities
    )

    # (b) generalized reconciliation-driven signal (WS2 semantics)
    ins = job_spec.insurance or {}
    network = ins.get("network_status")
    ins_emergency = ins.get("emergency_services", ins.get("emergency"))
    emergency = bool(ins_emergency)
    generalized_protected = (network == "in_network") or (
        emergency and nsa_bb_cfg.get("emergency_always_protected", True)
    )

    # Select the protection signal AND its own material-delta gate per path (fix
    # M1): inside the marker domain use the #67 min_impact; on the generalized WS2
    # path use nsa_balance_billing.tolerance_usd (they are independent statutory
    # theories with independently configured tolerances). When the marker domain
    # applies, the strict marker analysis governs — the broad generalized signal
    # does not get to fire a marker-shaped case the linkage rejected.
    if marker_context:
        protected = marker_protected
        min_impact = nsa_cfg.get("min_impact", 0)
    else:
        protected = generalized_protected
        min_impact = nsa_bb_cfg.get("tolerance_usd", 0)

    if (protected and eob_present and balance is not None and eob_resp is not None):
        impact = round(balance - eob_resp, 2)
        if impact > min_impact:
            if marker_context:
                # #67 marker path: preserve exact cpt + evidence (Nina's answer key).
                # `emergency` is DERIVED, not asserted: use the insurance flag when
                # present, else infer from the OON-marked line's own description
                # ("emergency ..."). Never contradict an explicit emergency=False
                # in the JobSpec (fix M3).
                nsa_cpt = oon_line.cpt
                if ins_emergency is not None:
                    marker_emergency = bool(ins_emergency)
                else:
                    marker_emergency = "emergency" in (oon_line.description or "").lower()
                nsa_evidence = {
                    "emergency": marker_emergency,
                    "facility_network_status": "in_network",
                    "provider_network_status": "out_of_network",
                    "statute": "No Surprises Act",
                }
            else:
                # WS2 generalized path: reconciliation-driven balance billing
                do_not_negotiate = config["thresholds"].get("nsa_do_not_negotiate", {})
                nsa_cpt = None
                nsa_evidence = {
                    "network_status": network,
                    "emergency": emergency,
                    "bill_patient_balance": balance,
                    "eob_patient_responsibility": eob_resp,
                    "do_not_negotiate": True,  # NSA violation → cite statute, file complaint
                    "action": do_not_negotiate.get("action", "cite_statute_and_file_complaint"),
                    "severity": "high",
                }
            flags.append(DerivedFlag(
                type="nsa",
                cpt=nsa_cpt,
                evidence=nsa_evidence,
                dollar_impact=impact,
            ))

    # ── denial: an EOB line the plan paid $0 on, carrying a denial/remark code. ─
    denial_codes = list(getattr(job_spec.eob, "denial_codes", []) or [])
    if eob_present and denial_codes:
        dn = rf.get("denial", {})
        min_amt = dn.get("min_amount", 0.0)
        # Only lines actually ON THE PATIENT'S BILL (reconciliation["matched"]) can
        # be a patient-owed denial — an eob_only line the provider absorbed/never
        # billed carries no dollars the patient owes on this statement (M5). And
        # only fire when the line carries a POSITIVE patient responsibility: a
        # bundled $0-liability line whose per-line responsibility is simply blank
        # (None) must NOT manufacture a billed-amount impact or inherit the claim's
        # other denial reason codes (M4).
        for row in reconciliation["matched"]:
            if row.get("plan_paid") != 0.0:
                continue
            impact = row.get("patient_responsibility")
            if impact is None or impact <= 0:
                continue
            if impact < min_amt:
                continue
            code = row.get("code")
            if code:
                implicated.add(_key(code, row.get("date")))
            flags.append(DerivedFlag(
                type="denial",
                cpt=code,
                evidence={
                    "date": row.get("date"),
                    "denial_codes": denial_codes,   # reason passthrough
                    "plan_paid": 0.0,
                    "patient_responsibility": row.get("patient_responsibility"),
                    "billed": row.get("billed"),
                },
                dollar_impact=round(impact, 2),
            ))

    # ── units_error: bill units above the EOB-allowed units, or above the
    #    code's plausible daily ceiling (config max_daily_units). ─────────────
    ue = rf.get("units_error", {})
    max_daily = ue.get("max_daily_units", {})
    # EOB-allowed units keyed by (code, date_of_service) — a code billed on several
    # dates has its OWN allowed figure per date; a code-only key would let one
    # date's ceiling overwrite (and be checked against) another's (fix H4).
    eob_units_by_key: dict[tuple, int] = {}
    for row in reconciliation["matched"]:
        if row.get("units_eob") is not None and row.get("code"):
            eob_units_by_key[_key(row["code"], row.get("date"))] = row["units_eob"]
    for li in lines:
        if _key(li.cpt, li.date_of_service) in implicated or li.billed_amount is None:
            continue
        units = li.units if li.units is not None else 1
        ceilings = []
        ekey = _key(li.cpt, li.date_of_service)
        has_eob_ceiling = ekey in eob_units_by_key
        if has_eob_ceiling:
            ceilings.append(eob_units_by_key[ekey])
        if li.cpt in max_daily:
            ceilings.append(max_daily[li.cpt])
        if not ceilings:
            continue
        allowed_units = min(ceilings)
        if units <= allowed_units:
            continue
        excess = units - allowed_units
        per_unit = (li.billed_amount or 0.0) / units if units else 0.0
        implicated.add(_key(li.cpt, li.date_of_service))
        flags.append(DerivedFlag(
            type="units_error",
            cpt=li.cpt,
            evidence={
                "billed_units": units,
                "allowed_units": allowed_units,
                "excess_units": excess,
                "basis": "eob_allowed" if has_eob_ceiling else "max_daily_units",
                "billed": li.billed_amount,
                "date": li.date_of_service,
            },
            dollar_impact=round(per_unit * excess, 2),
        ))

    # ── absent_from_chargemaster: a facility line with a standard code that is
    #    missing from an OTHERWISE-COMPLETE hospital MRF (45 CFR 180). Supporting
    #    lever only; NEVER fires for professional/physician-group lines. ────────
    if lookup is not None:
        ac = rf.get("absent_from_chargemaster", {})
        # Normalize the hospital key at the lookup boundary (strip surrounding
        # whitespace off the bill's facility_name), consistent with the payer/plan
        # normalization the lookup layer already does — trivial statement-header
        # noise (a trailing space from PDF extraction) must not silently make the
        # MRF-completeness gate dormant (fix L3).
        hospital = (job_spec.bill.facility_name or "").strip()
        std_types = set(ac.get("standard_code_types", ["CPT", "HCPCS", "DRG", "MS-DRG"]))
        distinct_codes = {li.cpt for li in lines if li.cpt}
        present = sum(1 for c in distinct_codes if lookup.code_in_chargemaster(hospital, c))
        mrf_complete = present >= ac.get("mrf_completeness_min_rows", 3)
        if mrf_complete:
            for li in lines:
                if _key(li.cpt, li.date_of_service) in implicated or li.billed_amount is None:
                    continue
                # Casefold/strip the entity gate — billing_entity is an
                # unconstrained Optional[str]; an extracted "Facility" is still a
                # facility line and must not fall to the professional branch (M8).
                if (li.billing_entity or "").strip().lower() != "facility":
                    continue  # professional/unknown → legitimately absent, do not flag
                if infer_code_type(li.cpt) not in std_types:
                    continue
                # UB-04 revenue codes are bare 3–4 digit numerics, shape-identical
                # to MS-DRG once a leading zero is lost in extraction (0450→450).
                # Don't accuse an ambiguous bare numeric of being an absent standard
                # code — CPT (5-digit)/HCPCS (letter+digits) are unaffected (fix M7).
                code_norm = (li.cpt or "").strip()
                if code_norm.isdigit() and len(code_norm) <= 4:
                    continue
                if lookup.code_in_chargemaster(hospital, li.cpt):
                    continue
                implicated.add(_key(li.cpt, li.date_of_service))
                flags.append(DerivedFlag(
                    type="absent_from_chargemaster",
                    cpt=li.cpt,
                    evidence={
                        "billed": li.billed_amount,
                        "code_type": infer_code_type(li.cpt),
                        "billing_entity": li.billing_entity,
                        "severity": ac.get("severity", "low"),
                        "mrf_codes_present": present,
                        "reason": "facility line not found in the hospital's posted standard-charges file",
                    },
                    dollar_impact=round(li.billed_amount, 2),
                ))

    # ── eob_mismatch: balance vs EOB patient responsibility (aggregate), plus
    #    per-line billed-vs-allowed detail from the reconciliation. ────────────
    eob_total = job_spec.eob.patient_responsibility_total
    if balance is not None and eob_total is not None:
        diff = round(balance - eob_total, 2)
        if diff > rf["eob_mismatch"]["tolerance_usd"]:
            evidence = {"bill": balance, "eob": eob_total}
            line_mismatches = [
                {"code": m["code"], "billed": m["billed"], "allowed": m["allowed"],
                 "billed_vs_allowed": m["billed_vs_allowed"]}
                for m in reconciliation["matched"]
                if m.get("billed_vs_allowed") is not None and m["billed_vs_allowed"] > 0
            ]
            if line_mismatches:  # only add when present, so the demo evidence is unchanged
                evidence["line_mismatches"] = line_mismatches
            flags.append(DerivedFlag(
                type="eob_mismatch",
                cpt=None,
                evidence=evidence,
                dollar_impact=diff,
            ))

    # ── markup: billed above the fair band's top (unflagged lines only) ───
    multiple = rf["markup"]["flag_above_band_multiple"]
    for li in lines:
        row = benchmarks.get(li.cpt)
        if row is None or _key(li.cpt, li.date_of_service) in implicated or li.billed_amount is None:
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
