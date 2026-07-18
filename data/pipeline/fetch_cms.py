"""Fetch Medicare rates for the demo CPT list. Owner: J.

Two acceptable paths (pick per time budget — see README Stage 1):
  A. Bulk: download PFS RVU quarterly ZIP + GPCI, compute payment = RVUs x CF (locality NC).
  B. Lookup: CMS PFS Look-Up Tool per demo code, hand-entered into data/raw/cms/pfs_lookup.csv
     (columns: cpt,setting,rate). Five codes — 10 minutes. Fine for the hackathon.

Either way transform.py only reads data/raw/cms/*.csv — the shape is the contract.
"""
import argparse
import json
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "raw" / "cms"
DEMO_CPTS_FILE = Path(__file__).resolve().parents[1] / "seed" / "demo_answer_key.json"


def demo_cpts() -> list[str]:
    with open(DEMO_CPTS_FILE) as f:
        return json.load(f)["demo_cpt_list"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["bulk", "lookup"], default="lookup")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Demo CPTs: {demo_cpts()}")
    if args.source == "lookup":
        print(f"Enter rates from the CMS PFS Look-Up Tool into {RAW_DIR}/pfs_lookup.csv (cpt,setting,rate)")
    else:
        # TODO(J): download PFS RVU ZIP + GPCI; filter to demo CPTs; write pfs_computed.csv
        raise SystemExit("bulk path not implemented yet — use --source lookup for now")


if __name__ == "__main__":
    main()
