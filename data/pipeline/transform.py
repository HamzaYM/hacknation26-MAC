"""Clean + transform raw CMS/MRF pulls into benchmarks.json, then validate. Owner: J.

Deterministic (PRD §7): all cleaning rules in README Stage 2, band math from
config/verticals/medical_bills.yaml. `--check` gates integration: it asserts the
seed reconciles with demo_answer_key.json so the demo numbers can never drift.
"""
import argparse
import json
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parents[1]
SEED = DATA_DIR / "seed"
CONFIG = DATA_DIR.parents[0] / "config" / "verticals" / "medical_bills.yaml"


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
    print(f"OK: {len(rows)} rows · Medicare total ${medicare_total} · MRF cash total ${cash_total} · arc reconciles")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate seed vs answer key")
    parser.add_argument("--report", action="store_true", help="print data-quality summary")
    args = parser.parse_args()

    if args.check:
        check()
        return
    # TODO(J): read data/raw/cms + data/raw/mrf -> clean (README Stage 2) -> compute bands ->
    # write SEED/benchmarks.json (validated against contracts/benchmark_row.schema.json) ->
    # upsert into Supabase `benchmarks`. Keep totals identical to the answer key.
    print("transform not implemented yet — run with --check to validate the current seed")


if __name__ == "__main__":
    main()
