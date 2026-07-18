#!/usr/bin/env python3
"""MRF → benchmark rows. Deterministic, zero LLM calls (PRD §7). Owner: J (engine by Kar Shin).

Streams a hospital price-transparency machine-readable file (CMS v2.x/v3.x CSV), filters
to the demo CPT list, applies the Stage-2 cleaning rules (data/pipeline/README.md), and
emits rows in the FROZEN contracts/benchmark_row.schema.json shape — ready for
data/seed/benchmarks.json and the Supabase `benchmarks` table.

Verified against Massachusetts General Hospital's CMS v3.0.0 file
(042697983_Massachusetts-General-Hospital_StandardCharges.csv, 60MB/159k rows, ~1s):
2 metadata rows → header with code|1..code|4 (+ code|N|type: CDM/CPT/RC/HCPCS/DRG/…),
tall payer/plan rows, CY2026 allowed-amount columns (median_amount, 10th/90th percentile).

Methodology (per PRD §10 + pipeline README Stage 2):
  * Multi-code columns: index CPT/HCPCS/DRG codes; ignore internal CDM/RC/LOCAL codes.
  * Payer-class segmentation: payer_name → commercial | medicare_advantage | medicaid |
    government_other. `mrf_negotiated_median` uses COMMERCIAL rows only (the RAND
    254%-of-Medicare comparison class). Unrecognized payers default to commercial —
    check the per-class counts in --report.
  * Setting filter: --setting outpatient keeps {outpatient, both} rows (demo = ER visit).
  * Modifier hygiene: drop -26 (professional) / TC (technical) component rows; other
    modifiers kept and logged.
  * Outlier policy: with a Medicare rate available, drop negotiated values <20% or >20x
    Medicare (data errors); counts logged.
  * Thin-data weighting: the `count` column ("1 through 10" → 5, else numeric) weights a
    weighted median, so single-claim rates don't swamp well-evidenced ones.
  * band_low/high = medicare_rate x multiples from config/verticals/medical_bills.yaml;
    fh_estimate = 2.54 x Medicare (RAND commercial norm), ALWAYS labeled estimated in UI.

Usage:
  python data/pipeline/mrf_extract.py \
      --mrf ~/mrf/042697983_Massachusetts-General-Hospital_StandardCharges.csv \
      --codes-from data/seed/demo_answer_key.json \
      --medicare data/raw/cms/medicare_ma.csv \
      --setting outpatient \
      --source-url "https://www.massgeneral.org/…/standardcharges.csv" \
      -o data/seed/benchmarks.json --report
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FH_ESTIMATE_MULTIPLE = 2.54          # RAND: commercial payers avg 254% of Medicare (2022)
OUTLIER_LOW_X_MEDICARE = 0.2         # pipeline README Stage 2
OUTLIER_HIGH_X_MEDICARE = 20.0
DROP_MODIFIERS = {"26", "TC"}        # professional/technical component splits
INDEXED_CODE_TYPES = {"CPT", "HCPCS", "DRG", "MS-DRG", "APR-DRG", "TRIS-DRG"}

# payer_name keyword → class. Checked in order; first hit wins; default commercial.
PAYER_CLASS_RULES = [
    ("medicaid", ["MEDICAID", "MASSHEALTH", "WELLSENSE", "PUBLIC PLANS", "MOLINA",
                  "COMMONWEALTH CARE", "HEALTH SAFETY NET"]),
    ("medicare_advantage", ["MEDICARE", "SENIOR", "ELDER", "HUMANA"]),
    ("government_other", ["TRICARE", "CHAMPVA", "VETERANS", " VA ", "CHAMPUS"]),
]

COLUMN_CANDIDATES = {
    "code": ["code|1", "code", "cpt", "cpt_code", "hcpcs", "procedure_code", "billing_code"],
    "description": ["description", "procedure_description", "charge_description"],
    "setting": ["setting"],
    "modifiers": ["modifiers", "modifier"],
    "gross": ["standard_charge|gross", "gross_charge", "standard_charge_gross"],
    "cash": ["standard_charge|discounted_cash", "discounted_cash", "cash_price", "standard_charge_discounted_cash"],
    "negotiated": ["standard_charge|negotiated_dollar", "negotiated_dollar", "payer_specific_negotiated_charge"],
    "allowed_median": ["median_amount"],
    "count": ["count"],
    "payer": ["payer_name", "payer"],
    "plan": ["plan_name", "plan"],
}

CODE_COL_RE = re.compile(r"^code\|(\d+)$")
MONEY_RE = re.compile(r"[^0-9.\-]")


def parse_money(raw):
    if raw is None:
        return None
    s = MONEY_RE.sub("", str(raw))
    if s in ("", "-", "."):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None


def parse_count(raw):
    """'1 through 10' → 5 (midpoint); numeric → numeric; blank/unparseable → 1."""
    if not raw:
        return 1
    s = str(raw).strip().lower()
    m = re.match(r"(\d+)\s*through\s*(\d+)", s)
    if m:
        return max(1, (int(m.group(1)) + int(m.group(2))) // 2)
    try:
        return max(1, int(float(s)))
    except ValueError:
        return 1


def payer_class(payer_name):
    up = f" {(payer_name or '').upper()} "
    for cls, keywords in PAYER_CLASS_RULES:
        if any(k in up for k in keywords):
            return cls
    return "commercial"


def weighted_median(pairs):
    """pairs: [(value, weight)] → weighted median, or None."""
    if not pairs:
        return None
    pairs = sorted(pairs)
    total = sum(w for _, w in pairs)
    acc = 0
    for v, w in pairs:
        acc += w
        if acc * 2 >= total:
            return v
    return pairs[-1][0]


def norm_header(h):
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def norm_code(c):
    return re.sub(r"\s+", "", str(c or "")).upper()


def load_band_multiples(config_path):
    text = Path(config_path).read_text()
    try:
        import yaml
        cfg = yaml.safe_load(text)["benchmark"]
        return cfg["band_low_multiple"], cfg["band_high_multiple"]
    except Exception:
        lo = re.search(r"band_low_multiple:\s*([\d.]+)", text)
        hi = re.search(r"band_high_multiple:\s*([\d.]+)", text)
        return float(lo.group(1)), float(hi.group(1))


def load_medicare(path):
    """CSV: code,rate (header row optional)."""
    rates = {}
    if not path:
        return rates
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            code, rate = norm_code(row[0]), parse_money(row[1])
            if code and rate and not code.startswith("CODE"):
                rates[code] = rate
    return rates


# ---------------------------------------------------------------------------
# Streaming MRF scan
# ---------------------------------------------------------------------------

def resolve_columns(header):
    normed = [norm_header(h) for h in header]
    pos = {h: i for i, h in enumerate(normed)}
    cols = {}
    for field, candidates in COLUMN_CANDIDATES.items():
        for cand in candidates:
            if cand in pos:
                cols[field] = pos[cand]
                break
    code_pairs = []
    for h, i in pos.items():
        m = CODE_COL_RE.match(h)
        if m:
            code_pairs.append((i, pos.get(f"code|{m.group(1)}|type")))
    if not code_pairs and "code" in cols:
        code_pairs = [(cols["code"], None)]
    return cols, sorted(code_pairs)


def cell(row, i):
    return row[i] if i is not None and len(row) > i else None


def scan_mrf(path, codes, setting, stats):
    """Returns {code: {"cash": [v..], "gross": [v..], "descriptions": set,
                       "negotiated": {payer_class: [(value, weight)..]},
                       "allowed": {payer_class: [(value, weight)..]}}}"""
    keep_settings = {"outpatient": {"outpatient", "both", ""},
                     "inpatient": {"inpatient", "both", ""},
                     "all": None}[setting]
    out = {c: {"cash": [], "gross": [], "descriptions": set(),
               "negotiated": defaultdict(list), "allowed": defaultdict(list)} for c in codes}

    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        header = cols = code_pairs = None
        for lineno, row in enumerate(reader):
            if header is None:
                normed = {norm_header(c) for c in row}
                if normed & set(COLUMN_CANDIDATES["description"]) and (
                        any(CODE_COL_RE.match(h) for h in normed) or normed & set(COLUMN_CANDIDATES["code"])):
                    header, (cols, code_pairs) = row, resolve_columns(row)
                elif lineno > 10:
                    sys.exit(f"ERROR: {path}: no recognizable header in first 10 rows — "
                             f"extend COLUMN_CANDIDATES for this hospital's layout.")
                continue
            stats["rows_scanned"] += 1
            hit_codes = set()
            for code_i, type_i in code_pairs:
                code = norm_code(cell(row, code_i))
                ctype = norm_code(cell(row, type_i)) if type_i is not None else ""
                if code in out and (not ctype or ctype in INDEXED_CODE_TYPES):
                    hit_codes.add(code)
            if not hit_codes:
                continue
            stats["rows_matched"] += 1

            if keep_settings is not None:
                s = (cell(row, cols.get("setting")) or "").strip().lower()
                if s not in keep_settings:
                    stats["dropped_setting"] += 1
                    continue
            mod = (cell(row, cols.get("modifiers")) or "").strip().upper()
            if mod in DROP_MODIFIERS:
                stats["dropped_modifier"] += 1
                continue
            if mod:
                stats["kept_other_modifier"][mod] += 1

            pclass = payer_class(cell(row, cols.get("payer")))
            stats["payer_class_rows"][pclass] += 1
            weight = parse_count(cell(row, cols.get("count")))
            negotiated = parse_money(cell(row, cols.get("negotiated")))
            allowed = parse_money(cell(row, cols.get("allowed_median")))
            cash = parse_money(cell(row, cols.get("cash")))
            gross = parse_money(cell(row, cols.get("gross")))
            desc = (cell(row, cols.get("description")) or "").strip()

            for code in hit_codes:
                entry = out[code]
                if negotiated is not None:
                    entry["negotiated"][pclass].append((negotiated, weight))
                if allowed is not None:
                    entry["allowed"][pclass].append((allowed, weight))
                if cash is not None:
                    entry["cash"].append(cash)
                if gross is not None:
                    entry["gross"].append(gross)
                if desc:
                    entry["descriptions"].add(desc)
    return out


# ---------------------------------------------------------------------------
# Benchmark-row assembly
# ---------------------------------------------------------------------------

def drop_outliers(pairs, medicare_rate, stats):
    if medicare_rate is None:
        return pairs
    kept = []
    for v, w in pairs:
        if v < OUTLIER_LOW_X_MEDICARE * medicare_rate or v > OUTLIER_HIGH_X_MEDICARE * medicare_rate:
            stats["dropped_outlier"] += 1
        else:
            kept.append((v, w))
    return kept


def build_rows(scan, medicare_rates, band_lo_x, band_hi_x, source_url, stats):
    rows = []
    for code in sorted(scan):
        entry = scan[code]
        medicare = medicare_rates.get(code)
        commercial = drop_outliers(entry["negotiated"].get("commercial", []), medicare, stats)
        neg_median = weighted_median(commercial)
        if neg_median is None:  # fall back to commercial allowed medians (CY2026 columns)
            allowed = drop_outliers(entry["allowed"].get("commercial", []), medicare, stats)
            neg_median = weighted_median(allowed)
            if neg_median is not None:
                stats["used_allowed_fallback"].append(code)
        cash = sorted(entry["cash"])[len(entry["cash"]) // 2] if entry["cash"] else None
        desc = min(entry["descriptions"], key=len) if entry["descriptions"] else ""

        if medicare is None:
            stats["missing_medicare"].append(code)
        row = {
            "cpt": code,
            "description": desc,
            "medicare_rate": medicare if medicare is not None else 0.0,
            "fh_estimate": round(medicare * FH_ESTIMATE_MULTIPLE, 2) if medicare else None,
            "mrf_cash": cash,
            "mrf_negotiated_median": round(neg_median, 2) if neg_median is not None else None,
            "band_low": round(medicare * band_lo_x, 2) if medicare else 0.0,
            "band_high": round(medicare * band_hi_x, 2) if medicare else 0.0,
            "source_url": source_url,
        }
        rows.append(row)
    return rows


def print_report(stats, rows):
    p = lambda *a: print(*a, file=sys.stderr)
    p("── data-quality report ─────────────────────────────")
    p(f"rows scanned: {stats['rows_scanned']:,} · matched demo codes: {stats['rows_matched']:,}")
    p(f"dropped — setting: {stats['dropped_setting']} · modifier(-26/TC): {stats['dropped_modifier']} · outliers: {stats['dropped_outlier']}")
    if stats["kept_other_modifier"]:
        p(f"kept rows with other modifiers: {dict(stats['kept_other_modifier'])}")
    p(f"payer-class rows: {dict(stats['payer_class_rows'])}")
    if stats["used_allowed_fallback"]:
        p(f"no commercial negotiated_dollar — used allowed-median fallback: {stats['used_allowed_fallback']}")
    if stats["missing_medicare"]:
        p(f"⚠ MISSING MEDICARE RATE (band/fh = 0/null — fix medicare CSV): {stats['missing_medicare']}")
    for r in rows:
        p(f"  {r['cpt']:>6}  cash {r['mrf_cash'] or 0:>9.2f} · neg-median {r['mrf_negotiated_median'] or 0:>9.2f}"
          f" · medicare {r['medicare_rate']:>8.2f} · band [{r['band_low']:.2f}, {r['band_high']:.2f}]  {r['description'][:40]}")
    p(f"totals — cash: {sum(r['mrf_cash'] or 0 for r in rows):.2f} · "
      f"neg-median: {sum(r['mrf_negotiated_median'] or 0 for r in rows):.2f} · "
      f"medicare: {sum(r['medicare_rate'] for r in rows):.2f}")


def main():
    root = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mrf", required=True, help="hospital MRF CSV path")
    ap.add_argument("--codes", help="comma-separated CPT/HCPCS list")
    ap.add_argument("--codes-from", help="JSON file with demo_cpt_list (e.g. data/seed/demo_answer_key.json)")
    ap.add_argument("--medicare", help="Medicare fee-schedule CSV (code,rate)")
    ap.add_argument("--setting", choices=["outpatient", "inpatient", "all"], default="outpatient")
    ap.add_argument("--source-url", default="", help="provenance URL stamped on every row")
    ap.add_argument("--config", default=str(root / "config/verticals/medical_bills.yaml"))
    ap.add_argument("-o", "--out", help="write benchmark rows JSON here (default stdout)")
    ap.add_argument("--report", action="store_true", help="print data-quality summary to stderr")
    args = ap.parse_args()

    if args.codes:
        codes = {norm_code(c) for c in args.codes.split(",") if c.strip()}
    elif args.codes_from:
        codes = set(json.loads(Path(args.codes_from).read_text())["demo_cpt_list"])
    else:
        sys.exit("ERROR: provide --codes or --codes-from")

    stats = {"rows_scanned": 0, "rows_matched": 0, "dropped_setting": 0, "dropped_modifier": 0,
             "dropped_outlier": 0, "kept_other_modifier": defaultdict(int),
             "payer_class_rows": defaultdict(int), "missing_medicare": [], "used_allowed_fallback": []}

    band_lo_x, band_hi_x = load_band_multiples(args.config)
    medicare = load_medicare(args.medicare)
    scan = scan_mrf(args.mrf, codes, args.setting, stats)
    rows = build_rows(scan, medicare, band_lo_x, band_hi_x, args.source_url, stats)

    if args.report:
        print_report(stats, rows)
    payload = json.dumps(rows, indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n")
        print(f"wrote {args.out} ({len(rows)} rows)", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
