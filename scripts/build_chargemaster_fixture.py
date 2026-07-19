"""One-off extraction: pull a small, real, committed slice of the chargemaster
SQLite DB into data/seed/chargemaster_test_extract.json for hermetic tests.

This is NOT run at test time or app boot — it is run once (by a human/agent)
whenever the fixture needs regenerating, against the full local chargemaster
DB. The output JSON is what tests/fixtures/mini_chargemaster.py loads to build
a tmp SQLite database, so `apps/api/tests/` never depends on the multi-hundred-
-thousand-row source file being present.

Sampling: for each (code, hospital) group, keep every row if the group has
<=4 rows; otherwise keep up to 1 government payer row (MEDICARE/MASSHEALTH/
MEDICAID/GOVERNMENT prefix) + up to 4 distinct commercial payers (alphabetical,
for determinism) — enough payer diversity to exercise cross_payer_stats'
outlier trim and payer-class split without shipping the full 1M-row table.

USAGE:
    python scripts/build_chargemaster_fixture.py \
        --db "c:/Users/jayva/Documents/My Web Sites/Hack Nation/chargemasters_demo.db" \
        --out data/seed/chargemaster_test_extract.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
from pathlib import Path

CODES = [
    "99281", "99282", "99283", "99284", "99285",
    "71045", "71046", "70450", "72110",
    "80048", "80053", "80061", "85025", "85027",
    "96360", "96361", "96374", "36415",
]

GOV_PREFIXES = ("MEDICARE", "MASSHEALTH", "MEDICAID", "GOVERNMENT")

COLUMNS = [
    "hospital_name", "hospital_ein", "ccn", "system", "city", "state",
    "setting", "code", "code_type", "description", "gross_charge",
    "cash_price", "payer_name", "plan_name", "negotiated_dollar",
    "negotiated_percentage", "negotiated_algorithm", "methodology",
    "min_negotiated", "max_negotiated", "estimated_amount",
]


def is_government(payer_name: str | None) -> bool:
    p = (payer_name or "").strip().upper()
    return any(p.startswith(prefix) for prefix in GOV_PREFIXES)


def sample_group(rows: list[dict], cap_commercial: int = 4) -> list[dict]:
    if len(rows) <= 4:
        return rows
    gov = [r for r in rows if is_government(r["payer_name"])]
    commercial = [r for r in rows if not is_government(r["payer_name"])]
    # one representative government row (prefer MEDICARE if present)
    gov_sorted = sorted(gov, key=lambda r: (0 if (r["payer_name"] or "").upper().startswith("MEDICARE") else 1, r["payer_name"] or ""))
    kept_gov = gov_sorted[:1]
    # diverse commercial payers, alphabetical for determinism, one row per distinct payer
    seen_payers: set[str] = set()
    kept_commercial = []
    for r in sorted(commercial, key=lambda r: (r["payer_name"] or "", r["plan_name"] or "")):
        key = r["payer_name"] or ""
        if key in seen_payers:
            continue
        seen_payers.add(key)
        kept_commercial.append(r)
        if len(kept_commercial) >= cap_commercial:
            break
    return kept_gov + kept_commercial


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="path to source chargemaster SQLite DB")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "seed" / "chargemaster_test_extract.json"))
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    placeholders = ",".join("?" * len(CODES))
    cur.execute(
        f"SELECT {', '.join(COLUMNS)} FROM charges "
        f"WHERE code IN ({placeholders}) AND code_type IN ('CPT','HCPCS') "
        f"ORDER BY code, hospital_name, payer_name, plan_name",
        CODES,
    )
    all_rows = [dict(r) for r in cur.fetchall()]

    groups: dict[tuple[str, str], list[dict]] = {}
    for r in all_rows:
        groups.setdefault((r["code"], r["hospital_name"]), []).append(r)

    kept: list[dict] = []
    for key in sorted(groups):
        kept.extend(sample_group(groups[key]))

    out = {
        "provenance": {
            "source_db": str(Path(args.db)),
            "extracted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "extraction_script": "scripts/build_chargemaster_fixture.py",
            "codes": CODES,
            "sampling": "<=4 rows/group kept whole; else 1 government + up to 4 distinct commercial payers",
            "total_rows_available": len(all_rows),
            "total_rows_kept": len(kept),
        },
        "rows": kept,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {len(kept)} rows (of {len(all_rows)} available) -> {out_path}")


if __name__ == "__main__":
    main()
