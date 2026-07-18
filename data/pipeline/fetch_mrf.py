"""Stream-filter hospital price-transparency MRFs to the demo CPT list. Owner: J.

MRFs are 100MB–GB; NEVER load whole files or commit raw. Stream (ijson for JSON,
csv reader for CSV), keep only rows whose code ∈ demo list, write the slim result
to data/raw/mrf/<hospital>.csv (columns: hospital,cpt,gross,cash,payer,negotiated).

Find files: "<hospital name> price transparency machine readable" — filename is
usually <EIN>_<name>_standardcharges.<ext>. Target 2–3 real NC systems.
"""
import argparse
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "raw" / "mrf"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="MRF URL to stream")
    parser.add_argument("--hospital", help="Short name for the output file")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # TODO(J): httpx stream -> ijson/csv filter to demo CPTs -> RAW_DIR / f"{args.hospital}.csv"
    print(f"TODO: stream {args.url} → {RAW_DIR}/{args.hospital}.csv (filtered to demo CPTs)")


if __name__ == "__main__":
    main()
