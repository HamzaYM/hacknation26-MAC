"""SqliteLookup — BenchmarkLookup backend against a local chargemaster SQLite
DB (tests / offline demo). Selected by BENCHMARK_SOURCE=sqlite.

DB path: env CHARGEMASTER_DB, else the shared demo DB used across this build
(881,668 real per-payer rows, 3 hospitals: MGH, Brigham & Women's,
Newton-Wellesley — see audit/chargemaster-profile.md). Tests point this at a
tmp DB built by apps/api/tests/fixtures/mini_chargemaster.py from committed,
real-data extracts — never the full source file.

Data gotchas handled defensively (per audit/chargemaster-profile.md):
  - Every numeric column is TEXT (`gross_charge`, `cash_price`,
    `negotiated_dollar`, etc.) — parsed via `_num()`, which also tolerates
    the literal string `'None'`, `''`, `'N/A'`, `'n/a'`, `'NULL'`.
  - `code_type` includes CDM/RC duplicate-noise rows (same line item keyed
    two ways) and sparse LOCAL/TRIS-DRG rows — queries restrict to
    `code_type IN ('CPT','HCPCS','DRG','MS-DRG')`.
  - `estimated_amount` is 100% null across the whole table — never read.

cross_payer_stats: commercial rows only — government payers (MEDICARE,
MASSHEALTH, MEDICAID, GOVERNMENT* prefixes on `payer_name`) excluded, then
outlier-trimmed (drop rows < 20% or > 20x the RAW median, i.e. computed
before trimming) before computing percentiles over the surviving rows.

medicare_rate: reads a `medicare_rates` table from the same SQLite file when
present (tests' mini DB has one, staged from data/seed/medicare_rates.json);
falls back to the committed data/seed/medicare_rates.json directly when the
connected DB has no such table (e.g. pointed at the raw chargemasters_demo.db,
which is chargemaster-only) — so BENCHMARK_SOURCE=sqlite against either DB
still returns real, provenance-carrying Medicare rates.
"""
from __future__ import annotations

import json
import os
import sqlite3
import statistics
import threading
from functools import lru_cache
from pathlib import Path

from .lookup import ChargeRow, MedicareRate

REPO_ROOT = Path(__file__).resolve().parents[4]  # engine/ -> app/ -> api/ -> apps/ -> repo root
DEFAULT_CHARGEMASTER_DB = "c:/Users/jayva/Documents/My Web Sites/Hack Nation/chargemasters_demo.db"
MEDICARE_SEED = REPO_ROOT / "data" / "seed" / "medicare_rates.json"

STANDARD_CODE_TYPES = ("CPT", "HCPCS", "DRG", "MS-DRG")
GOV_PREFIXES = ("MEDICARE", "MASSHEALTH", "MEDICAID", "GOVERNMENT")


def _num(value) -> float | None:
    """Defensive TEXT->float: handles None, the literal string 'None', '',
    'N/A'/'n/a', 'NULL', and genuinely malformed numeric strings."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.upper() in ("NONE", "N/A", "NA", "NULL"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _is_government(payer_name: str | None) -> bool:
    p = (payer_name or "").strip().upper()
    return any(p.startswith(prefix) for prefix in GOV_PREFIXES)


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Nearest-rank-free linear-interpolation percentile over an already-
    sorted list (0 <= pct <= 100)."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


@lru_cache(maxsize=1)
def _load_medicare_seed() -> dict[tuple[str, str], dict]:
    """Committed data/seed/medicare_rates.json, keyed (code, component).
    Process-wide cache — this file is static within a run."""
    if not MEDICARE_SEED.exists():
        return {}
    with open(MEDICARE_SEED, encoding="utf-8") as f:
        data = json.load(f)
    return {(r["code"], r["component"]): r for r in data.get("rows", [])}


class SqliteLookup:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get("CHARGEMASTER_DB", DEFAULT_CHARGEMASTER_DB)
        self._available = Path(self.db_path).exists()
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._charge_cache: dict[tuple[str, str], list[ChargeRow]] = {}
        self._has_medicare_table: bool | None = None

    # -- connection -----------------------------------------------------
    def _connect(self) -> sqlite3.Connection | None:
        if not self._available:
            return None
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _query(self, sql: str, params: tuple) -> list[sqlite3.Row]:
        conn = self._connect()
        if conn is None:
            return []
        with self._lock:
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur.fetchall()

    # -- charge rows (cached per hospital+code) --------------------------
    def charge_rows(self, hospital: str, code: str) -> list[ChargeRow]:
        key = (hospital, code)
        if key in self._charge_cache:
            return self._charge_cache[key]
        placeholders = ",".join("?" * len(STANDARD_CODE_TYPES))
        raw = self._query(
            f"SELECT hospital_name, code, code_type, description, setting, gross_charge, "
            f"cash_price, payer_name, plan_name, negotiated_dollar, negotiated_percentage, "
            f"min_negotiated, max_negotiated, methodology FROM charges "
            f"WHERE hospital_name = ? AND code = ? AND code_type IN ({placeholders})",
            (hospital, code, *STANDARD_CODE_TYPES),
        )
        rows = [
            ChargeRow(
                hospital=r["hospital_name"], code=r["code"], code_type=r["code_type"],
                description=r["description"], setting=r["setting"],
                gross_charge=_num(r["gross_charge"]), cash_price=_num(r["cash_price"]),
                payer_name=r["payer_name"], plan_name=r["plan_name"],
                negotiated_dollar=_num(r["negotiated_dollar"]),
                negotiated_percentage=_num(r["negotiated_percentage"]),
                min_negotiated=_num(r["min_negotiated"]), max_negotiated=_num(r["max_negotiated"]),
                methodology=r["methodology"],
            )
            for r in raw
        ]
        self._charge_cache[key] = rows
        return rows

    def gross_charge(self, hospital: str, code: str) -> float | None:
        # Constant per (hospital, code) per audit/chargemaster-profile.md — first non-null wins.
        for row in self.charge_rows(hospital, code):
            if row.gross_charge is not None:
                return row.gross_charge
        return None

    def cash_price(self, hospital: str, code: str) -> float | None:
        for row in self.charge_rows(hospital, code):
            if row.cash_price is not None:
                return row.cash_price
        return None

    def plan_rate(self, hospital: str, code: str, payer_name: str,
                  plan_name: str | None = None) -> float | None:
        target_payer = (payer_name or "").strip().upper()
        candidates = [
            r for r in self.charge_rows(hospital, code)
            if (r.payer_name or "").strip().upper() == target_payer
        ]
        if plan_name:
            target_plan = plan_name.strip().upper()
            plan_matches = [r for r in candidates if (r.plan_name or "").strip().upper() == target_plan]
            if plan_matches:
                candidates = plan_matches
        for r in candidates:
            if r.negotiated_dollar is not None:
                return r.negotiated_dollar
            if r.negotiated_percentage is not None and r.gross_charge is not None:
                return round(r.negotiated_percentage / 100 * r.gross_charge, 2)
        return None

    def cross_payer_stats(self, hospital: str, code: str) -> dict | None:
        rows = self.charge_rows(hospital, code)
        commercial_vals: list[tuple[float, str]] = []  # (value, payer_name)
        for r in rows:
            if _is_government(r.payer_name):
                continue
            val = r.negotiated_dollar
            if val is None and r.negotiated_percentage is not None and r.gross_charge is not None:
                val = round(r.negotiated_percentage / 100 * r.gross_charge, 2)
            if val is not None and val > 0:
                commercial_vals.append((val, r.payer_name or ""))
        if not commercial_vals:
            return None

        raw_values = [v for v, _ in commercial_vals]
        raw_median = statistics.median(raw_values)
        if raw_median > 0:
            lo, hi = raw_median * 0.2, raw_median * 20
            surviving = [(v, p) for v, p in commercial_vals if lo <= v <= hi]
        else:
            surviving = commercial_vals
        if not surviving:
            return None

        vals_sorted = sorted(v for v, _ in surviving)
        n_payers = len({p for _, p in surviving})
        return {
            "p25": round(_percentile(vals_sorted, 25), 2),
            "median": round(_percentile(vals_sorted, 50), 2),
            "p75": round(_percentile(vals_sorted, 75), 2),
            "min": round(vals_sorted[0], 2),
            "max": round(vals_sorted[-1], 2),
            "n_payers": n_payers,
            "n_rows": len(surviving),
        }

    # -- medicare ---------------------------------------------------------
    def _medicare_table_available(self) -> bool:
        if self._has_medicare_table is not None:
            return self._has_medicare_table
        rows = self._query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='medicare_rates'", ()
        )
        self._has_medicare_table = bool(rows)
        return self._has_medicare_table

    def medicare_rate(self, code: str, component: str = "global") -> MedicareRate | None:
        if self._medicare_table_available():
            rows = self._query(
                "SELECT code, value, formula, source_url, version FROM medicare_rates "
                "WHERE code = ? AND component = ?",
                (code, component),
            )
            if rows:
                r = rows[0]
                return MedicareRate(code=r["code"], component=component, value=float(r["value"]),
                                     formula=r["formula"], source_url=r["source_url"],
                                     version=r["version"] or "sqlite:medicare_rates")
        seed_row = _load_medicare_seed().get((code, component))
        if seed_row:
            return MedicareRate(code=code, component=component, value=float(seed_row["value"]),
                                 formula=seed_row.get("formula"), source_url=seed_row.get("source_url"),
                                 version=seed_row.get("version", "seed:medicare_rates.json"))
        return None

    def code_in_chargemaster(self, hospital: str, code: str) -> bool:
        return len(self.charge_rows(hospital, code)) > 0

    def hospitals(self) -> list[str]:
        rows = self._query("SELECT DISTINCT hospital_name FROM charges ORDER BY hospital_name", ())
        return [r["hospital_name"] for r in rows]

    def version(self) -> str:
        return f"sqlite:{Path(self.db_path).name}"
