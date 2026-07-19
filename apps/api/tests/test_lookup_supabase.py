"""SupabaseLookup: protocol conformance (shared with test_lookup_sqlite.py)
+ fail-soft tests, run hermetically (no network) by monkeypatching the
lowest-level `_query()` method to execute against a tmp SQLite DB built from
the SAME committed real-data fixture as test_lookup_sqlite.py, instead of a
real psycopg2/Postgres connection. This proves SupabaseLookup's query
construction, cross_payer_stats math, and result-shaping logic are correct
and identical to SqliteLookup's, without requiring a live database in CI.

A second, separate test (`test_supabase_live_smoke`) exercises the REAL
psycopg2 path against the live Supabase project and is skipped cleanly when
SUPABASE_DB_URL isn't set (CI-safe either way, per the task brief).
"""
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
from lookup_conformance import BWH, run_conformance_checks  # noqa: E402
from mini_chargemaster import build_mini_chargemaster_db  # noqa: E402

from app.engine.lookup_supabase import SupabaseLookup  # noqa: E402


def _num(value):
    """Mirrors lookup_sqlite._num — used only to make the sqlite-backed fake
    look like real Postgres NUMERIC columns (which never contain TEXT junk)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.upper() in ("NONE", "N/A", "NA", "NULL"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


NUMERIC_COLS = {"gross_charge", "cash_price", "negotiated_dollar", "negotiated_percentage",
                 "min_negotiated", "max_negotiated"}


class _SqliteBackedQuery:
    """Stands in for SupabaseLookup._query: same signature (sql, params) ->
    list[dict], but executes against a sqlite3 connection built from the
    mini chargemaster fixture, translating psycopg2 %s placeholders to
    sqlite3's ? and chargemaster_charges -> charges. Numeric TEXT columns
    are coerced through _num() to emulate real Postgres NUMERIC (never a
    TEXT 'None'/'n/a' — that gotcha is sqlite-source-only)."""

    def __init__(self, db_path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

    def __call__(self, sql: str, params: tuple) -> list[dict]:
        cur = self.conn.cursor()
        if "information_schema.tables" in sql:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medicare_rates'")
            return [dict(r) for r in cur.fetchall()]
        is_charges_query = "chargemaster_charges" in sql
        sqlite_sql = sql.replace("chargemaster_charges", "charges").replace("%s", "?")
        cur.execute(sqlite_sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        if is_charges_query:
            for r in rows:
                for col in NUMERIC_COLS:
                    if col in r:
                        r[col] = _num(r[col])
        return rows


@pytest.fixture()
def lookup(tmp_path, monkeypatch) -> SupabaseLookup:
    db_path = build_mini_chargemaster_db(tmp_path / "mini_chargemaster.db")
    lk = SupabaseLookup()
    monkeypatch.setattr(lk, "_query", _SqliteBackedQuery(db_path))
    return lk


def test_supabase_lookup_protocol_conformance(lookup: SupabaseLookup) -> None:
    run_conformance_checks(lookup)


def test_defensive_handling_when_no_db_url(monkeypatch) -> None:
    """Never crash, never print/leak SUPABASE_DB_URL; every method degrades
    to None/[]/False when the env var is unset."""
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    lk = SupabaseLookup()
    assert lk.available() is False
    assert lk.charge_rows(BWH, "36415") == []
    assert lk.gross_charge(BWH, "36415") is None
    assert lk.cross_payer_stats(BWH, "36415") is None
    assert lk.medicare_rate("99283") is None
    assert lk.code_in_chargemaster(BWH, "36415") is False
    assert lk.hospitals() == []
    assert isinstance(lk.version(), str)


def test_factory_wiring_returns_supabase_backend(monkeypatch) -> None:
    monkeypatch.setenv("BENCHMARK_SOURCE", "supabase")
    from app.engine.lookup import get_lookup
    lk = get_lookup()
    assert isinstance(lk, SupabaseLookup)


@pytest.mark.skipif(not os.environ.get("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL not set — skipping live smoke test")
def test_supabase_live_smoke() -> None:
    """Exercises the real psycopg2 path against the live project. Only runs
    when SUPABASE_DB_URL is present in the environment; asserts on shapes/
    presence only, never prints the connection string."""
    lk = SupabaseLookup()
    assert lk.available() is True
    hospitals = lk.hospitals()
    assert "Massachusetts General Hospital" in hospitals
    gross = lk.gross_charge("Massachusetts General Hospital", "99283")
    assert gross is not None and gross > 0
    stats = lk.cross_payer_stats("Massachusetts General Hospital", "99283")
    assert stats is not None and stats["n_rows"] >= 1
    rate = lk.medicare_rate("99283", "professional")
    assert rate is not None and 65 <= rate.value <= 80
