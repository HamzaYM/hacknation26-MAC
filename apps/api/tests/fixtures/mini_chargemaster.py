"""Builds a tmp SQLite chargemaster DB from the committed, real-data fixture
(data/seed/chargemaster_test_extract.json — ~200 real rows pulled once from
the full chargemasters_demo.db, see scripts/build_chargemaster_fixture.py)
plus data/seed/medicare_rates.json, so `apps/api/tests/` never needs the
multi-hundred-thousand-row source DB present on disk.

NOTE on the "fixtures" name: `apps/api/tests/fixtures.py` (a module, demo job
spec helpers) and `apps/api/tests/fixtures/` (this package, chargemaster
test data) coexist in the same directory. This subpackage intentionally has
NO `__init__.py` — Python's path-based finder resolves a plain `fixtures.py`
module ahead of a namespace-package directory of the same name, so
`from fixtures import clean_job_spec` (used throughout the existing suite)
keeps resolving to the module, unaffected. Import this file directly by path
or by adding this directory to sys.path, e.g.:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
    from mini_chargemaster import build_mini_chargemaster_db

Do NOT add an `__init__.py` here — it would shadow `tests/fixtures.py` and
break every existing `from fixtures import ...` in the suite.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CHARGEMASTER_EXTRACT = REPO_ROOT / "data" / "seed" / "chargemaster_test_extract.json"
MEDICARE_RATES = REPO_ROOT / "data" / "seed" / "medicare_rates.json"

CHARGES_COLUMNS = [
    "hospital_name", "hospital_ein", "ccn", "system", "city", "state",
    "setting", "code", "code_type", "description", "gross_charge",
    "cash_price", "payer_name", "plan_name", "negotiated_dollar",
    "negotiated_percentage", "negotiated_algorithm", "methodology",
    "min_negotiated", "max_negotiated", "estimated_amount",
]


def build_mini_chargemaster_db(db_path: str | Path, include_medicare: bool = True) -> Path:
    """Create (or overwrite) a SQLite file at db_path with `charges`,
    `coverage`, and (if include_medicare and the seed exists) `medicare_rates`
    tables, populated from the committed real-data fixtures. All `charges`
    numeric columns are TEXT, matching the live chargemasters_demo.db schema
    exactly (the "TEXT columns, 'None' strings" gotcha the lookup layer must
    parse defensively) — plus one synthetic 'None'-string row and one
    malformed-number row appended so the defensive parsing is exercised even
    though the real extract happens to be clean.
    """
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()

    with open(CHARGEMASTER_EXTRACT, encoding="utf-8") as f:
        extract = json.load(f)
    rows = list(extract["rows"])

    # Real chargemasters are noisy (per audit/chargemaster-profile.md); the
    # sampled 217-row extract happens not to contain a 'None'-string or
    # malformed numeric value, so we append two synthetic noise rows,
    # clearly marked, to exercise the defensive-parsing path in tests.
    if rows:
        template = rows[0]
        noise_none_string = {**template, "payer_name": "NOISE TEST PAYER [9999]",
                              "plan_name": "NOISE TEST PLAN", "negotiated_dollar": "None",
                              "gross_charge": "None", "cash_price": "None",
                              "min_negotiated": "None", "max_negotiated": "None"}
        noise_malformed = {**template, "payer_name": "NOISE TEST PAYER 2 [9998]",
                            "plan_name": "NOISE TEST PLAN 2", "negotiated_dollar": "n/a",
                            "gross_charge": "", "cash_price": "N/A"}
        rows = rows + [noise_none_string, noise_malformed]

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(f"CREATE TABLE charges ({', '.join(c + ' TEXT' for c in CHARGES_COLUMNS)})")
    cur.executemany(
        f"INSERT INTO charges ({', '.join(CHARGES_COLUMNS)}) VALUES ({', '.join('?' * len(CHARGES_COLUMNS))})",
        [tuple(r.get(c) for c in CHARGES_COLUMNS) for r in rows],
    )
    cur.execute("CREATE INDEX idx_charges_hospital_code ON charges (hospital_name, code)")
    cur.execute("CREATE INDEX idx_charges_code ON charges (code)")
    cur.execute("CREATE INDEX idx_charges_payer ON charges (code, payer_name)")

    cur.execute("CREATE TABLE coverage (hospital_name TEXT, rows INTEGER, status TEXT, error TEXT)")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["hospital_name"]] = counts.get(r["hospital_name"], 0) + 1
    cur.executemany(
        "INSERT INTO coverage (hospital_name, rows, status, error) VALUES (?,?,?,?)",
        [(h, n, "ok", None) for h, n in counts.items()],
    )

    if include_medicare and MEDICARE_RATES.exists():
        with open(MEDICARE_RATES, encoding="utf-8") as f:
            mc = json.load(f)
        cur.execute("""
            CREATE TABLE medicare_rates (
                code TEXT, code_type TEXT, component TEXT, value REAL,
                formula TEXT, source TEXT, source_url TEXT, file_version TEXT,
                locality TEXT, label TEXT, version TEXT
            )
        """)
        cur.executemany(
            "INSERT INTO medicare_rates (code, code_type, component, value, formula, source, "
            "source_url, file_version, locality, label, version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(r["code"], r.get("code_type", "CPT"), r["component"], r["value"], r.get("formula"),
              r.get("source"), r.get("source_url"), r.get("file_version"), r.get("locality"),
              r.get("label"), r.get("version")) for r in mc["rows"]],
        )

    conn.commit()
    conn.close()
    return db_path
