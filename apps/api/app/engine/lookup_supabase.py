"""SupabaseLookup — BenchmarkLookup backend against live Postgres
(chargemaster_charges / chargemaster_coverage / medicare_rates). Selected by
BENCHMARK_SOURCE=supabase.

Lazy-connect, fail-soft: no connection is opened at import or construction
time; every method opens (or reuses) a connection on first use and returns
None/[]/False on any connection or query error rather than raising — same
best-effort contract as apps/api/app/db.py (never required for boot).

Credentials: read ONLY from os.environ["SUPABASE_DB_URL"]; never logged,
never hardcoded. Identical query semantics to lookup_sqlite.SqliteLookup
(same outlier trim, same government-payer exclusion, same code_type filter)
so fixture/sqlite/supabase are interchangeable from the caller's POV — the
live table's numeric columns are already Postgres NUMERIC (no TEXT-parsing
gotchas here, unlike the sqlite source).
"""
from __future__ import annotations

import logging
import os
import statistics
import threading
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from .lookup import ChargeRow, MedicareRate

log = logging.getLogger("negotiator.lookup_supabase")

STANDARD_CODE_TYPES = ("CPT", "HCPCS", "DRG", "MS-DRG")
GOV_PREFIXES = ("MEDICARE", "MASSHEALTH", "MEDICAID", "GOVERNMENT")


def _is_government(payer_name: str | None) -> bool:
    p = (payer_name or "").strip().upper()
    return any(p.startswith(prefix) for prefix in GOV_PREFIXES)


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


class SupabaseLookup:
    def __init__(self):
        self._lock = threading.Lock()
        self._conn: Any = None
        self._warned = False
        self._charge_cache: dict[tuple[str, str], list[ChargeRow]] = {}
        self._has_medicare_table: bool | None = None

    # -- connection (mirrors app/db.py's best-effort pattern) ------------
    def _connect(self):
        url = os.environ.get("SUPABASE_DB_URL", "").strip()
        if not url:
            return None
        return psycopg2.connect(url, connect_timeout=10)

    def _get_conn(self):
        with self._lock:
            if self._conn is not None and not self._conn.closed:
                return self._conn
            try:
                self._conn = self._connect()
                if self._conn is not None:
                    self._conn.autocommit = True
                elif not self._warned:
                    log.warning("SUPABASE_DB_URL not set — SupabaseLookup disabled (fail-soft: None/[]/False)")
                    self._warned = True
            except Exception as err:  # noqa: BLE001 — any connect failure means "no DB"
                if not self._warned:
                    log.warning("Supabase unreachable — SupabaseLookup disabled: %s", str(err).splitlines()[0])
                    self._warned = True
                self._conn = None
            return self._conn

    def _query(self, sql: str, params: tuple) -> list[dict]:
        conn = self._get_conn()
        if conn is None:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as err:
            log.warning("Supabase connection lost, dropping it: %s", str(err).splitlines()[0])
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None
            return []
        except psycopg2.Error as err:
            log.warning("Supabase query skipped: %s", str(err).splitlines()[0])
            return []

    def available(self) -> bool:
        return self._get_conn() is not None

    # -- charge rows (cached per hospital+code) --------------------------
    def charge_rows(self, hospital: str, code: str) -> list[ChargeRow]:
        # Normalize the hospital key (strip surrounding whitespace), consistent with
        # the payer/plan .strip().upper() handling below and SqliteLookup (L3).
        hospital = (hospital or "").strip()
        key = (hospital, code)
        if key in self._charge_cache:
            return self._charge_cache[key]
        placeholders = ",".join(["%s"] * len(STANDARD_CODE_TYPES))
        raw = self._query(
            f"SELECT hospital_name, code, code_type, description, setting, gross_charge, "
            f"cash_price, payer_name, plan_name, negotiated_dollar, negotiated_percentage, "
            f"min_negotiated, max_negotiated, methodology FROM chargemaster_charges "
            f"WHERE hospital_name = %s AND code = %s AND code_type IN ({placeholders})",
            (hospital, code, *STANDARD_CODE_TYPES),
        )
        rows = [
            ChargeRow(
                hospital=r["hospital_name"], code=r["code"], code_type=r["code_type"],
                description=r["description"], setting=r["setting"],
                gross_charge=float(r["gross_charge"]) if r["gross_charge"] is not None else None,
                cash_price=float(r["cash_price"]) if r["cash_price"] is not None else None,
                payer_name=r["payer_name"], plan_name=r["plan_name"],
                negotiated_dollar=float(r["negotiated_dollar"]) if r["negotiated_dollar"] is not None else None,
                negotiated_percentage=float(r["negotiated_percentage"]) if r["negotiated_percentage"] is not None else None,
                min_negotiated=float(r["min_negotiated"]) if r["min_negotiated"] is not None else None,
                max_negotiated=float(r["max_negotiated"]) if r["max_negotiated"] is not None else None,
                methodology=r["methodology"],
            )
            for r in raw
        ]
        self._charge_cache[key] = rows
        return rows

    def gross_charge(self, hospital: str, code: str) -> float | None:
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
        commercial_vals: list[tuple[float, str]] = []
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

    # -- medicare -----------------------------------------------------
    def _medicare_table_available(self) -> bool:
        if self._has_medicare_table is not None:
            return self._has_medicare_table
        rows = self._query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
            "AND table_name='medicare_rates'", ()
        )
        self._has_medicare_table = bool(rows)
        return self._has_medicare_table

    def medicare_rate(self, code: str, component: str = "global") -> MedicareRate | None:
        if not self._medicare_table_available():
            return None
        rows = self._query(
            "SELECT code, value, formula, source_url, version FROM medicare_rates "
            "WHERE code = %s AND component = %s LIMIT 1",
            (code, component),
        )
        if not rows:
            return None
        r = rows[0]
        return MedicareRate(code=r["code"], component=component, value=float(r["value"]),
                             formula=r["formula"], source_url=r["source_url"],
                             version=r["version"] or "supabase:medicare_rates")

    def code_in_chargemaster(self, hospital: str, code: str) -> bool:
        return len(self.charge_rows(hospital, code)) > 0

    def hospitals(self) -> list[str]:
        rows = self._query("SELECT DISTINCT hospital_name FROM chargemaster_charges ORDER BY hospital_name", ())
        return [r["hospital_name"] for r in rows]

    def version(self) -> str:
        return "supabase:chargemaster_charges"
