"""Clean + transform raw CMS/MRF pulls into benchmarks.json, then validate. Owner: J.

Deterministic (PRD §7): all cleaning rules in README Stage 2, band math from
config/verticals/medical_bills.yaml. `--check` gates integration: it asserts the
seed reconciles with demo_answer_key.json so the demo numbers can never drift.

USAGE:
    python transform.py --check          # validate current seed vs answer key
    python transform.py --transform      # run full pipeline: raw -> benchmarks.json
    python transform.py --transform --freeze-demo   # same, but keep frozen demo mrf values
    python transform.py --report         # print data-quality summary from MRF pulls

--freeze-demo mechanism (generalized-pipeline WS1):
    Historically `transform()` computed real MRF stats from data/raw/mrf/*.csv
    when present, logged them, and then SILENTLY OVERWROTE them with the
    hand-engineered benchmarks_v0.json values "for Mercy General consistency"
    — i.e. even fresh real data never reached the output row. That override now
    only happens when `--freeze-demo` is explicitly passed. By DEFAULT,
    `--transform` uses freshly computed MRF stats whenever raw data is present
    for a code, falling back to the frozen seed value only when no raw MRF data
    exists for that code (unchanged either way).
    `--check` is unaffected by this flag: it validates benchmarks_v0.json (the
    committed, hand-locked demo seed) directly, never benchmarks.json, so the
    demo answer-key gate stays green regardless of --freeze-demo or of whether
    data/raw/mrf/*.csv happens to be present on the machine running it.
"""
import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parents[1]
SEED = DATA_DIR / "seed"
RAW_CMS = DATA_DIR / "raw" / "cms"
RAW_MRF = DATA_DIR / "raw" / "mrf"
CONFIG = DATA_DIR.parents[0] / "config" / "verticals" / "medical_bills.yaml"
CONTRACTS = DATA_DIR.parents[0] / "contracts" / "benchmark_row.schema.json"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- Stage 2: Clean

def clean_code(code: str) -> str:
    """Normalize CPT: strip modifiers (99283-25 -> 99283), whitespace."""
    return code.strip().split("-")[0].split(" ")[0]


def is_valid_rate(rate: float, medicare_rate: float) -> bool:
    """Outlier policy: negotiated rates < 20% of Medicare or > 20x Medicare are data errors."""
    if medicare_rate <= 0:
        return rate > 0
    return (rate >= medicare_rate * 0.2) and (rate <= medicare_rate * 20)


def load_cms_rates() -> dict[str, dict]:
    """Load CMS rates from pfs_lookup.csv."""
    rates = {}
    csv_path = RAW_CMS / "pfs_lookup.csv"
    if not csv_path.exists():
        return rates
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cpt = clean_code(row["cpt"])
            rates[cpt] = {
                "medicare_rate": float(row["combined_rate"]),
                "pfs_rate": float(row["pfs_rate"]) if row.get("pfs_rate") else None,
                "opps_facility": float(row["opps_facility"]) if row.get("opps_facility") else None,
                "clfs_rate": float(row["clfs_rate"]) if row.get("clfs_rate") else None,
                "source_notes": row.get("source_notes", ""),
            }
    return rates


def load_mrf_data() -> dict[str, list[dict]]:
    """Load all MRF extracts from data/raw/mrf/*.csv, grouped by CPT."""
    by_cpt: dict[str, list[dict]] = {}
    if not RAW_MRF.exists():
        return by_cpt
    for csv_path in RAW_MRF.glob("*.csv"):
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cpt = clean_code(row.get("cpt", ""))
                if not cpt:
                    continue
                by_cpt.setdefault(cpt, []).append(row)
    return by_cpt


def compute_mrf_stats(rows: list[dict], medicare_rate: float) -> dict:
    """Compute cash price and negotiated median from MRF rows, with cleaning."""
    cash_prices = []
    negotiated_rates = []
    dropped = {"outlier": 0, "zero_or_neg": 0, "missing": 0}

    for row in rows:
        # Cash price
        cash_str = (row.get("cash") or "").strip()
        if cash_str:
            try:
                cash = float(cash_str)
                if cash <= 0:
                    dropped["zero_or_neg"] += 1
                elif not is_valid_rate(cash, medicare_rate):
                    dropped["outlier"] += 1
                else:
                    cash_prices.append(cash)
            except ValueError:
                dropped["missing"] += 1

        # Negotiated rate
        neg_str = (row.get("negotiated") or "").strip()
        if neg_str:
            try:
                neg = float(neg_str)
                if neg <= 0:
                    dropped["zero_or_neg"] += 1
                elif not is_valid_rate(neg, medicare_rate):
                    dropped["outlier"] += 1
                else:
                    negotiated_rates.append(neg)
            except ValueError:
                dropped["missing"] += 1

    result = {
        "mrf_cash": round(statistics.median(cash_prices), 2) if cash_prices else None,
        "mrf_negotiated_median": round(statistics.median(negotiated_rates), 2) if negotiated_rates else None,
        "n_cash_obs": len(cash_prices),
        "n_neg_obs": len(negotiated_rates),
        "dropped": dropped,
    }
    return result


# --------------------------------------------------------------------------- Stage 3: Transform

def compute_benchmark_row(cpt: str, description: str, medicare_rate: float,
                          mrf_cash: float, mrf_neg_median: float,
                          cfg: dict, source_url: str) -> dict:
    """Compute one benchmark row with band math."""
    band_low_mult = cfg["band_low_multiple"]
    band_high_mult = cfg["band_high_multiple"]

    # FAIR Health estimate: paywalled, approximate as RAND commercial norm (2.54x Medicare)
    fh_estimate = round(medicare_rate * 2.54, 2) if medicare_rate else None

    return {
        "cpt": cpt,
        "description": description,
        "medicare_rate": medicare_rate,
        "fh_estimate": fh_estimate,
        "mrf_cash": mrf_cash,
        "mrf_negotiated_median": mrf_neg_median,
        "band_low": round(medicare_rate * band_low_mult, 2),
        "band_high": round(medicare_rate * band_high_mult, 2),
        "source_url": source_url,
    }


# --------------------------------------------------------------------------- Check (Stage 4)

def check() -> None:
    with open(SEED / "benchmarks_v0.json") as f:
        rows = {r["cpt"]: r for r in json.load(f)}
    with open(SEED / "demo_answer_key.json") as f:
        key = json.load(f)
    with open(CONFIG) as f:
        cfg = yaml.safe_load(f)["benchmark"]

    errors: list[str] = []
    for cpt in key["demo_cpt_list"]:
        if cpt not in rows:
            errors.append(f"missing benchmark row for demo CPT {cpt}")
    medicare_total = round(sum(r["medicare_rate"] for r in rows.values()), 2)
    if medicare_total != key["expected_totals"]["medicare_total"]:
        errors.append(f"Medicare total {medicare_total} != answer key {key['expected_totals']['medicare_total']}")
    cash_total = round(sum(r["mrf_cash"] for r in rows.values()), 2)
    if cash_total != key["expected_totals"]["mrf_cash_total"]:
        errors.append(f"MRF cash total {cash_total} != answer key {key['expected_totals']['mrf_cash_total']}")
    neg_median_total = round(sum(r["mrf_negotiated_median"] for r in rows.values()), 2)
    if neg_median_total != key["expected_totals"]["mrf_negotiated_median_total"]:
        errors.append(f"MRF neg-median total {neg_median_total} != answer key {key['expected_totals']['mrf_negotiated_median_total']}")
    for r in rows.values():
        if round(r["band_low"], 2) != round(r["medicare_rate"] * cfg["band_low_multiple"], 2):
            errors.append(f"{r['cpt']} band_low != medicare x {cfg['band_low_multiple']}")
        if round(r["band_high"], 2) != round(r["medicare_rate"] * cfg["band_high_multiple"], 2):
            errors.append(f"{r['cpt']} band_high != medicare x {cfg['band_high_multiple']}")
    arc = key["negotiation_arc"]
    if arc["balance"] - key["seeded_flags"][0]["dollar_impact"] != arc["after_duplicate_concession"]:
        errors.append("arc arithmetic: balance - duplicate != after_duplicate_concession")

    if errors:
        raise SystemExit("CHECK FAILED:\n  - " + "\n  - ".join(errors))
    print(f"OK: {len(rows)} rows \u00b7 Medicare total ${medicare_total} \u00b7 MRF cash total ${cash_total} \u00b7 arc reconciles")


# --------------------------------------------------------------------------- Report

def report() -> None:
    """Print data-quality summary from MRF pulls."""
    cms_rates = load_cms_rates()
    mrf_data = load_mrf_data()

    with open(SEED / "demo_answer_key.json") as f:
        demo_cpts = json.load(f)["demo_cpt_list"]

    print("=== DATA QUALITY REPORT ===\n")
    print(f"CMS rates loaded: {len(cms_rates)} codes")
    print(f"MRF data loaded: {sum(len(v) for v in mrf_data.values())} total rows across {len(mrf_data)} codes\n")

    for cpt in demo_cpts:
        print(f"--- CPT {cpt} ---")
        if cpt in cms_rates:
            r = cms_rates[cpt]
            print(f"  Medicare combined: ${r['medicare_rate']:.2f}")
        else:
            print("  Medicare: NOT FOUND")

        if cpt in mrf_data:
            rows = mrf_data[cpt]
            medicare_rate = cms_rates.get(cpt, {}).get("medicare_rate", 100)
            stats = compute_mrf_stats(rows, medicare_rate)
            print(f"  MRF observations: {len(rows)} raw rows")
            print(f"  Cash prices: {stats['n_cash_obs']} valid -> median ${stats['mrf_cash']}" if stats['mrf_cash'] else "  Cash prices: none")
            print(f"  Negotiated rates: {stats['n_neg_obs']} valid -> median ${stats['mrf_negotiated_median']}" if stats['mrf_negotiated_median'] else "  Negotiated rates: none")
            if any(stats["dropped"].values()):
                print(f"  Dropped: {stats['dropped']}")
        else:
            print("  MRF: NO DATA")
        print()


# --------------------------------------------------------------------------- Full transform

def transform(freeze_demo: bool = False) -> None:
    """Full pipeline: read raw CMS + MRF -> clean -> compute -> write benchmarks.json.

    freeze_demo=True reproduces the historical behavior (real computed MRF
    stats logged but discarded in favor of the frozen benchmarks_v0.json
    values); freeze_demo=False (default) lets real computed stats flow into
    the output row whenever raw MRF data is present for that code."""
    with open(CONFIG) as f:
        cfg = yaml.safe_load(f)["benchmark"]
    with open(SEED / "demo_answer_key.json") as f:
        key = json.load(f)

    cms_rates = load_cms_rates()
    mrf_data = load_mrf_data()
    demo_cpts = key["demo_cpt_list"]

    # Load existing benchmarks for descriptions and fallback values
    with open(SEED / "benchmarks_v0.json") as f:
        existing = {r["cpt"]: r for r in json.load(f)}

    benchmarks = []
    for cpt in demo_cpts:
        desc = existing.get(cpt, {}).get("description", f"CPT {cpt}")
        medicare_rate = cms_rates.get(cpt, {}).get("medicare_rate")
        source = cms_rates.get(cpt, {}).get("source_notes", "")

        # Use existing medicare_rate as fallback (engineered to hit $438 total)
        if medicare_rate is None:
            medicare_rate = existing[cpt]["medicare_rate"]
            log(f"  {cpt}: using existing medicare_rate ${medicare_rate} (no raw CMS data)")

        # MRF stats
        mrf_cash = existing[cpt].get("mrf_cash")
        mrf_neg_median = existing[cpt].get("mrf_negotiated_median")

        if cpt in mrf_data:
            stats = compute_mrf_stats(mrf_data[cpt], medicare_rate)
            if freeze_demo:
                if stats["mrf_cash"] is not None:
                    log(f"  {cpt}: real MRF cash ${stats['mrf_cash']} (n={stats['n_cash_obs']}) computed, "
                        f"but --freeze-demo active -> keeping frozen demo value ${mrf_cash}")
                if stats["mrf_negotiated_median"] is not None:
                    log(f"  {cpt}: real MRF negotiated median ${stats['mrf_negotiated_median']} "
                        f"(n={stats['n_neg_obs']}) computed, but --freeze-demo active -> keeping frozen value ${mrf_neg_median}")
            else:
                if stats["mrf_cash"] is not None:
                    mrf_cash = stats["mrf_cash"]
                    log(f"  {cpt}: using real computed MRF cash ${mrf_cash} (n={stats['n_cash_obs']})")
                if stats["mrf_negotiated_median"] is not None:
                    mrf_neg_median = stats["mrf_negotiated_median"]
                    log(f"  {cpt}: using real computed MRF negotiated median ${mrf_neg_median} (n={stats['n_neg_obs']})")

        row = compute_benchmark_row(
            cpt=cpt,
            description=desc,
            medicare_rate=medicare_rate,
            mrf_cash=mrf_cash,
            mrf_neg_median=mrf_neg_median,
            cfg=cfg,
            source_url=source if source else existing[cpt].get("source_url", ""),
        )
        benchmarks.append(row)

    # Write output
    out_path = SEED / "benchmarks.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmarks, f, indent=2)
    log(f"\nWrote {len(benchmarks)} benchmark rows -> {out_path}")

    # Validate totals
    medicare_total = round(sum(r["medicare_rate"] for r in benchmarks), 2)
    cash_total = round(sum(r["mrf_cash"] for r in benchmarks), 2)
    log(f"Medicare total: ${medicare_total} (expected: ${key['expected_totals']['medicare_total']})")
    log(f"MRF cash total: ${cash_total} (expected: ${key['expected_totals']['mrf_cash_total']})")

    if medicare_total != key["expected_totals"]["medicare_total"]:
        log("WARNING: Medicare total mismatch! Update answer key or adjust rates.")
    if cash_total != key["expected_totals"]["mrf_cash_total"]:
        log("WARNING: MRF cash total mismatch! Update answer key or adjust rates.")


# --------------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate seed vs answer key")
    parser.add_argument("--report", action="store_true", help="print data-quality summary")
    parser.add_argument("--transform", action="store_true", help="run full pipeline")
    parser.add_argument("--freeze-demo", action="store_true",
                        help="with --transform: keep frozen benchmarks_v0.json mrf values instead of "
                             "real computed stats (historical behavior; see header docstring)")
    args = parser.parse_args()

    if args.check:
        check()
        return
    if args.report:
        report()
        return
    if args.transform:
        transform(freeze_demo=args.freeze_demo)
        return
    # Default: show usage
    print("Run with --check, --report, or --transform. Use --help for details.")


if __name__ == "__main__":
    main()
