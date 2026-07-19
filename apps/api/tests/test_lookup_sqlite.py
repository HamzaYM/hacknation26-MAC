"""SqliteLookup: protocol conformance (shared with test_lookup_supabase.py)
+ backend-specific defensive-parsing and factory-wiring tests.

Hermetic: builds a tmp SQLite DB from the committed real-data fixture
(data/seed/chargemaster_test_extract.json + medicare_rates.json) — never
touches the multi-hundred-thousand-row source chargemasters_demo.db.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
from lookup_conformance import BWH, run_conformance_checks  # noqa: E402
from mini_chargemaster import build_mini_chargemaster_db  # noqa: E402

from app.engine.lookup_sqlite import SqliteLookup  # noqa: E402


@pytest.fixture()
def lookup(tmp_path) -> SqliteLookup:
    db_path = build_mini_chargemaster_db(tmp_path / "mini_chargemaster.db")
    return SqliteLookup(str(db_path))


def test_sqlite_lookup_protocol_conformance(lookup: SqliteLookup) -> None:
    run_conformance_checks(lookup)


def test_defensive_parsing_of_noise_rows(lookup: SqliteLookup) -> None:
    """The mini DB's synthetic noise rows use TEXT 'None'/'n/a'/'' for
    numeric columns — _num() must treat them as missing, not crash and not
    silently become 0.0 or NaN."""
    rows = lookup.charge_rows(BWH, "36415")
    noise_rows = [r for r in rows if "NOISE TEST" in (r.payer_name or "")]
    assert len(noise_rows) == 2
    for r in noise_rows:
        assert r.negotiated_dollar is None
    # first noise row: gross_charge/cash_price also 'None' string -> None
    assert noise_rows[0].gross_charge is None
    assert noise_rows[0].cash_price is None
    # second noise row: gross_charge='' -> None, cash_price='N/A' -> None
    assert noise_rows[1].gross_charge is None
    assert noise_rows[1].cash_price is None


def test_no_medicare_rates_table_falls_back_to_seed_json(tmp_path) -> None:
    """When pointed at a chargemaster DB with no medicare_rates table
    (e.g. the raw chargemasters_demo.db, which is chargemaster-only),
    SqliteLookup must fall back to the committed data/seed/medicare_rates.json
    rather than returning None for every code."""
    db_path = build_mini_chargemaster_db(tmp_path / "no_medicare.db", include_medicare=False)
    lk = SqliteLookup(str(db_path))
    rate = lk.medicare_rate("99283", "professional")
    assert rate is not None
    assert rate.value == 72.74
    assert "seed" in rate.version or "cms" in rate.version


def test_missing_db_file_is_fail_soft(tmp_path) -> None:
    """CHARGEMASTER_DB pointed at a nonexistent path must never crash, and
    must never silently create an empty sqlite file at that path either."""
    missing_path = tmp_path / "does_not_exist.db"
    lk = SqliteLookup(str(missing_path))
    assert lk.charge_rows(BWH, "36415") == []
    assert lk.gross_charge(BWH, "36415") is None
    assert lk.cross_payer_stats(BWH, "36415") is None
    assert lk.code_in_chargemaster(BWH, "36415") is False
    assert lk.hospitals() == []
    assert not missing_path.exists(), "SqliteLookup must not create the DB file just by querying it"


def test_factory_wiring_returns_sqlite_backend(monkeypatch, tmp_path) -> None:
    """get_lookup() with BENCHMARK_SOURCE=sqlite must return a SqliteLookup
    instance (the seam wired in apps/api/app/engine/lookup.py)."""
    db_path = build_mini_chargemaster_db(tmp_path / "factory.db")
    monkeypatch.setenv("BENCHMARK_SOURCE", "sqlite")
    monkeypatch.setenv("CHARGEMASTER_DB", str(db_path))
    from app.engine.lookup import get_lookup
    lk = get_lookup()
    assert isinstance(lk, SqliteLookup)
    assert lk.gross_charge(BWH, "36415") == 16.0
