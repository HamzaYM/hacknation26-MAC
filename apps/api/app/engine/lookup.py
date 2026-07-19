"""Benchmark lookup layer — the single seam between the engine and price data.

Three backends behind one protocol, selected by BENCHMARK_SOURCE:
  fixture  (default) — wraps the 5-CPT seed exactly as today; zero external
                       services, keeps offline boot and existing tests green.
  sqlite             — local SQLite chargemaster + medicare_rates (tests/offline).
  supabase           — live Postgres (runtime; product decision #7).

All backends return identical shapes. Chargemaster data is stable context and
cached in-process per (hospital, code); case data never flows through here.
Every returned number carries enough context for the caller to build a full
provenance Anchor (see contracts/anchor_set.schema.json).

Contract doc: docs/generalized-pipeline.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

from ..fixtures import demo_benchmarks

# Hospital the 5-CPT fixture seed rows describe (real MGH MRF extracts).
FIXTURE_HOSPITAL = "Massachusetts General Hospital"


@dataclass(frozen=True)
class ChargeRow:
    """One chargemaster row (one payer/plan for one code at one hospital)."""
    hospital: str
    code: str
    code_type: str
    description: str | None
    setting: str | None
    gross_charge: float | None
    cash_price: float | None
    payer_name: str | None
    plan_name: str | None
    negotiated_dollar: float | None
    negotiated_percentage: float | None
    min_negotiated: float | None
    max_negotiated: float | None
    methodology: str | None


@dataclass(frozen=True)
class MedicareRate:
    """A computed Medicare rate with its provenance."""
    code: str
    component: str  # professional | facility | global
    value: float
    formula: str | None
    source_url: str | None
    version: str  # e.g. "PFS 2026Q1 locality MA-01" or "fixture-seed"


class BenchmarkLookup(Protocol):
    """Stages 3-6 of the pipeline, as queries. None means 'no data' — callers
    map that to coverage statuses, never to invented numbers."""

    def charge_rows(self, hospital: str, code: str) -> list[ChargeRow]: ...

    def gross_charge(self, hospital: str, code: str) -> float | None: ...

    def cash_price(self, hospital: str, code: str) -> float | None: ...

    def plan_rate(self, hospital: str, code: str, payer_name: str,
                  plan_name: str | None = None) -> float | None: ...

    def cross_payer_stats(self, hospital: str, code: str) -> dict | None:
        """{p25, median, p75, min, max, n_payers, n_rows} over commercial
        negotiated_dollar rows, outlier-trimmed. None if no usable rows."""
        ...

    def medicare_rate(self, code: str, component: str = "global") -> MedicareRate | None: ...

    def code_in_chargemaster(self, hospital: str, code: str) -> bool: ...

    def hospitals(self) -> list[str]: ...

    def version(self) -> str:
        """Data-version string for provenance (answer keys pin this)."""
        ...


class FixtureLookup:
    """Wraps data/seed/benchmarks_v0.json — the exact data the app runs on
    today. Single hospital (MGH), 5 CPTs, no per-payer rows."""

    def _row(self, code: str) -> dict | None:
        return demo_benchmarks().get(code)

    def charge_rows(self, hospital: str, code: str) -> list[ChargeRow]:
        r = self._row(code)
        if not r or hospital != FIXTURE_HOSPITAL:
            return []
        return [ChargeRow(
            hospital=FIXTURE_HOSPITAL, code=code, code_type="CPT",
            description=r.get("description"), setting=None,
            gross_charge=None, cash_price=r.get("mrf_cash"),
            payer_name=None, plan_name=None,
            negotiated_dollar=r.get("mrf_negotiated_median"),
            negotiated_percentage=None, min_negotiated=None,
            max_negotiated=None, methodology="fixture seed median",
        )]

    def gross_charge(self, hospital: str, code: str) -> float | None:
        return None  # seed has no gross charges

    def cash_price(self, hospital: str, code: str) -> float | None:
        r = self._row(code)
        return r.get("mrf_cash") if r and hospital == FIXTURE_HOSPITAL else None

    def plan_rate(self, hospital: str, code: str, payer_name: str,
                  plan_name: str | None = None) -> float | None:
        return None  # seed has no payer dimension

    def cross_payer_stats(self, hospital: str, code: str) -> dict | None:
        r = self._row(code)
        if not r or hospital != FIXTURE_HOSPITAL:
            return None
        med = r.get("mrf_negotiated_median")
        if med is None:
            return None
        return {"p25": med, "median": med, "p75": med,
                "min": med, "max": med, "n_payers": 1, "n_rows": 1}

    def medicare_rate(self, code: str, component: str = "global") -> MedicareRate | None:
        r = self._row(code)
        if not r or r.get("medicare_rate") is None:
            return None
        return MedicareRate(code=code, component="global",
                            value=float(r["medicare_rate"]),
                            formula=None, source_url=r.get("source_url"),
                            version="fixture-seed (synthetic, pre-locality)")

    def code_in_chargemaster(self, hospital: str, code: str) -> bool:
        return hospital == FIXTURE_HOSPITAL and self._row(code) is not None

    def hospitals(self) -> list[str]:
        return [FIXTURE_HOSPITAL]

    def version(self) -> str:
        return "fixture:benchmarks_v0"


def get_lookup() -> BenchmarkLookup:
    """Backend factory. WS1 registers the sqlite and supabase backends here;
    unknown/unconfigured values fall back to fixture so boot never breaks."""
    source = os.environ.get("BENCHMARK_SOURCE", "fixture")
    if source == "sqlite":
        try:
            from .lookup_sqlite import SqliteLookup  # provided by WS1
            return SqliteLookup()
        except ImportError:
            pass
    if source == "supabase":
        try:
            from .lookup_supabase import SupabaseLookup  # provided by WS1
            return SupabaseLookup()
        except ImportError:
            pass
    return FixtureLookup()
