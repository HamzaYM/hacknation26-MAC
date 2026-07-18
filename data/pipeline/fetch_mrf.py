"""Stream-filter hospital price-transparency MRFs to the demo CPT list. Owner: J.

MRFs are 100MB-GB; NEVER load whole files or commit raw. Stream (ijson for JSON,
csv reader for CSV), keep only rows whose code in demo list, write the slim result
to data/raw/mrf/<hospital>.csv (columns: hospital,cpt,setting,description,gross,cash,payer,plan,negotiated).

Find files: "<hospital name> price transparency machine readable" -- filename is
usually <EIN>_<name>_standardcharges.<ext>. Target 2-3 real NC systems.

USAGE:
    python fetch_mrf.py --all          # fetch both Atrium + Novant (default targets)
    python fetch_mrf.py --url URL --hospital name --format csv|json
"""
import argparse
import csv
import io
import json
import sys
from pathlib import Path

import httpx

RAW_DIR = Path(__file__).resolve().parents[1] / "raw" / "mrf"
DEMO_CPTS_FILE = Path(__file__).resolve().parents[1] / "seed" / "demo_answer_key.json"

# Pre-configured NC hospital MRF sources (web-verified 2026-07)
TARGETS = [
    {
        "hospital": "atrium_carolinas_medical_center",
        "display_name": "Atrium Health Carolinas Medical Center (Charlotte NC)",
        "url": "https://sthpiprd.blob.core.windows.net/machine-readable-files/11170/561398929-1295789907_carolinas-medical-center_standardcharges.csv",
        "format": "csv",
    },
    {
        "hospital": "novant_presbyterian",
        "display_name": "Novant Health Presbyterian Medical Center (Charlotte NC)",
        "url": "https://www2.novanthealth.org/Public_Files/regulatory/560554230_the-presbyterian-hospital-dba-novant-health-presbyterian-medical-center_standardcharges.json",
        "format": "json",
    },
]


def demo_cpts() -> set[str]:
    with open(DEMO_CPTS_FILE) as f:
        return set(json.load(f)["demo_cpt_list"])


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def stream_filter_csv(url: str, hospital: str, cpts: set[str], out_path: Path) -> int:
    """Stream a CMS v2.x CSV MRF, keep only rows matching demo CPTs."""
    log(f"  Streaming CSV: {url[:80]}...")
    rows_kept = 0

    with httpx.stream("GET", url, timeout=300, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; negotiator-pipeline/1.0)"}) as resp:
        resp.raise_for_status()
        lines = resp.iter_lines()

        # Find header row (CMS files may have metadata rows before the real header)
        header = None
        for line in lines:
            cols = next(csv.reader(io.StringIO(line)))
            low = [c.strip().lower() for c in cols]
            if "description" in low and any("code" in c or "standard_charge" in c for c in low):
                header = cols
                break
        if not header:
            log("    !! No CMS header found")
            return 0

        low = [c.strip().lower() for c in header]
        idx = {c: i for i, c in enumerate(low)}

        # Find code columns
        code_indices = []
        for i, c in enumerate(low):
            if c.startswith("code") and "|type" not in c and c != "code_type":
                code_indices.append(i)
        if not code_indices and "code" in idx:
            code_indices = [idx["code"]]

        desc_i = idx.get("description")
        setting_i = idx.get("setting")
        gross_i = idx.get("standard_charge|gross")
        cash_i = idx.get("standard_charge|discounted_cash")
        payer_i = idx.get("payer_name")
        plan_i = idx.get("plan_name")
        neg_i = idx.get("standard_charge|negotiated_dollar")

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["hospital", "cpt", "setting", "description", "gross", "cash", "payer", "plan", "negotiated"])

            for line in lines:
                try:
                    row = next(csv.reader(io.StringIO(line)))
                except StopIteration:
                    continue
                # Check if any code column matches our demo CPTs
                matched_cpt = None
                for ci in code_indices:
                    if ci < len(row):
                        code = row[ci].strip().split("-")[0]  # strip modifiers
                        if code in cpts:
                            matched_cpt = code
                            break
                if not matched_cpt:
                    continue

                def cell(i):
                    return row[i].strip() if (i is not None and i < len(row)) else ""

                writer.writerow([
                    hospital,
                    matched_cpt,
                    cell(setting_i),
                    cell(desc_i)[:120],
                    cell(gross_i),
                    cell(cash_i),
                    cell(payer_i),
                    cell(plan_i),
                    cell(neg_i),
                ])
                rows_kept += 1
    return rows_kept


def stream_filter_json(url: str, hospital: str, cpts: set[str], out_path: Path) -> int:
    """Stream a CMS JSON MRF using ijson, keep only items matching demo CPTs."""
    import ijson

    log(f"  Streaming JSON: {url[:80]}...")
    rows_kept = 0

    with httpx.stream("GET", url, timeout=600, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; negotiator-pipeline/1.0)"}) as resp:
        resp.raise_for_status()

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["hospital", "cpt", "setting", "description", "gross", "cash", "payer", "plan", "negotiated"])

            # CMS JSON schema: top-level "standard_charge_information" array
            # Each item has code_information[], description, standard_charges[]
            parser = ijson.items(resp.stream, "standard_charge_information.item")

            for item in parser:
                codes = item.get("code_information") or []
                matched_cpts = []
                for c in codes:
                    code = (c.get("code") or "").strip().split("-")[0]
                    if code in cpts:
                        matched_cpts.append(code)
                if not matched_cpts:
                    continue

                desc = (item.get("description") or "")[:120]
                for sc in item.get("standard_charges", []):
                    setting = sc.get("setting") or ""
                    gross = sc.get("gross_charge") or ""
                    cash = sc.get("discounted_cash") or ""
                    payers = sc.get("payers_information") or []
                    if not payers:
                        for cpt in matched_cpts:
                            writer.writerow([hospital, cpt, setting, desc, gross, cash, "", "", ""])
                            rows_kept += 1
                    for p in payers:
                        for cpt in matched_cpts:
                            writer.writerow([
                                hospital, cpt, setting, desc, gross, cash,
                                p.get("payer_name", ""),
                                p.get("plan_name", ""),
                                p.get("standard_charge_dollar") or "",
                            ])
                            rows_kept += 1
    return rows_kept


def fetch_one(url: str, hospital: str, fmt: str, cpts: set[str]) -> int:
    """Fetch and filter one MRF. Returns row count."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / f"{hospital}.csv"

    if fmt == "csv":
        n = stream_filter_csv(url, hospital, cpts, out_path)
    elif fmt == "json":
        n = stream_filter_json(url, hospital, cpts, out_path)
    else:
        log(f"  !! Unknown format: {fmt}")
        return 0

    log(f"  -> {n} rows kept -> {out_path}")
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="MRF URL to stream")
    parser.add_argument("--hospital", help="Short name for the output file")
    parser.add_argument("--format", choices=["csv", "json"], help="File format")
    parser.add_argument("--all", action="store_true", help="Fetch all pre-configured NC targets")
    args = parser.parse_args()

    cpts = demo_cpts()
    log(f"Demo CPTs: {sorted(cpts)}")

    if args.all or (not args.url):
        for t in TARGETS:
            log(f"\n[{t['display_name']}]")
            try:
                fetch_one(t["url"], t["hospital"], t["format"], cpts)
            except Exception as e:
                log(f"  !! ERROR: {e}")
    else:
        if not args.hospital or not args.format:
            parser.error("--hospital and --format required when using --url")
        fetch_one(args.url, args.hospital, args.format, cpts)


if __name__ == "__main__":
    main()
