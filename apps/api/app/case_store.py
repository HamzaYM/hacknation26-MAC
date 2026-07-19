"""Case-scoped store — replaces the deepcopy(DEMO_JOB_SPEC) merge.

In-memory, case_id-keyed storage for the artifacts a case accumulates as it
moves through the pipeline: job_spec (bill+EOB), flags, benchmark_report
(contracts/anchor_set.schema.json), dossier, and allowed_numbers (the citable
set the honesty audit checks call transcripts against).

Maya's fixture is the automatic fallback for DEMO_CASE_ID so the demo path and
offline boot behave exactly as before. Supabase persistence, when configured,
is write-through and additive — never required for boot (best-effort DB rule).

Contract doc: docs/generalized-pipeline.md.
"""
from __future__ import annotations

import copy
import threading
from typing import Any

from .fixtures import DEMO_CASE_ID

_lock = threading.Lock()
_store: dict[str, dict[str, Any]] = {}

# Keys a case can hold. Kept explicit so callers can't typo new ad-hoc slots.
SLOTS = ("job_spec", "flags", "benchmark_report", "dossier", "allowed_numbers",
         "scenario_id", "answer_key")


def put(case_id: str, slot: str, value: Any) -> None:
    if slot not in SLOTS:
        raise KeyError(f"unknown case slot {slot!r}; add it to case_store.SLOTS deliberately")
    with _lock:
        _store.setdefault(case_id, {})[slot] = value


def get(case_id: str, slot: str, default: Any = None) -> Any:
    if slot not in SLOTS:
        raise KeyError(f"unknown case slot {slot!r}")
    with _lock:
        case = _store.get(case_id)
        if case and slot in case:
            return case[slot]
    if case_id == DEMO_CASE_ID:
        return _demo_fallback(slot, default)
    return default


def get_job_spec(case_id: str) -> dict | None:
    """Convenience: stored job_spec, else a fresh copy of Maya's fixture for
    the demo case, else None. Callers own the returned copy."""
    spec = get(case_id, "job_spec")
    return copy.deepcopy(spec) if spec is not None else None


def known_cases() -> list[str]:
    with _lock:
        return list(_store.keys())


def clear(case_id: str | None = None) -> None:
    """Test helper. Clears one case or the whole store."""
    with _lock:
        if case_id is None:
            _store.clear()
        else:
            _store.pop(case_id, None)


def _demo_fallback(slot: str, default: Any) -> Any:
    """Maya's fixture values, imported lazily to avoid import cycles."""
    from .fixtures import DEMO_JOB_SPEC
    if slot == "job_spec":
        return copy.deepcopy(DEMO_JOB_SPEC)
    return default
