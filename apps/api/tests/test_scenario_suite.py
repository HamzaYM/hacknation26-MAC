"""WS4 scenario-suite regression tests.

For every committed scenario in data/scenarios/, re-run the REAL engine pipeline
(detect_flags + build_benchmark_report over a hermetic SqliteLookup built from
the committed real-data extract) and assert it reproduces the committed answer
key EXACTLY — flags (type/code/dollar_impact), the full BenchmarkReport, and the
ask surface. Plus:

  · sc01 reproduces data/seed/demo_answer_key.json's LOCKED numbers (Maya through
    the generalized flow);
  · sc05/sc08 carry ZERO error flags (pure benchmarking);
  · `generate.py --check` confirms byte-identical artifacts;
  · the /scenarios endpoints round-trip (GET lists 9; POST load stores the
    answer key's own numbers on the case);
  · the case-generic simulator's spoken dollar figures are all citable — the
    honesty invariant, pre-call.

Hermetic: the lookup is built from data/seed/chargemaster_test_extract.json +
medicare_rates.json, identical to how data/scenarios/generate.py seeded the
suite, so no network and no giant source DB are touched.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "data" / "scenarios"))

import generate as scen_gen  # noqa: E402  — data/scenarios/generate.py

from app import case_store  # noqa: E402
from app.config import load_vertical  # noqa: E402
from app.engine.anchors import build_benchmark_report  # noqa: E402
from app.engine.dossier import build_dossier  # noqa: E402
from app.engine.flags import detect_flags, load_ncci_table  # noqa: E402
from app.fixtures import DEMO_JOB_SPEC, demo_benchmarks, demo_flags  # noqa: E402
from app.models import JobSpec  # noqa: E402
from app.simulator import build_generic_sequence  # noqa: E402

SCEN_DIR = REPO_ROOT / "data" / "scenarios"
SCENARIO_IDS = sorted(p.name for p in SCEN_DIR.iterdir()
                      if p.is_dir() and (p / "scenario.json").exists())
FLAG_SCENARIO_IDS = [s for s in SCENARIO_IDS if s not in ("sc05_self_pay_gross",
                                                          "sc08_clean_overpriced")]

_DOLLAR_RE = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)")


def _load(sid: str, name: str) -> dict:
    with open(SCEN_DIR / sid / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def config() -> dict:
    return load_vertical()


@pytest.fixture(scope="module")
def ncci(config) -> dict:
    return load_ncci_table(config)


@pytest.fixture(scope="module")
def lookup():
    # Identical construction to data/scenarios/generate.py — same rows, same
    # fixed DB basename → the same lookup.version() the answer keys were pinned
    # with, so BenchmarkReport.data_version matches byte-for-byte.
    return scen_gen.build_scenario_lookup()


@pytest.fixture(autouse=True)
def _clear_case_store():
    yield
    case_store.clear()


def test_suite_has_nine_scenarios():
    assert len(SCENARIO_IDS) == 9


# ── the core answer-key assertion: real pipeline == committed answer key ────
@pytest.mark.parametrize("sid", SCENARIO_IDS)
def test_pipeline_reproduces_answer_key(sid, lookup, config, ncci):
    spec_dict = _load(sid, "job_spec.json")
    ak = _load(sid, "answer_key.json")
    js = JobSpec.model_validate(spec_dict)

    flags = detect_flags(js, config, demo_benchmarks(), ncci, lookup=lookup)
    report = build_benchmark_report(js, lookup, config)

    # flags: type + code + dollar_impact (+ any evidence-derived detail) exact
    assert scen_gen.serialize_flags(flags) == ak["expected_flags"], f"{sid}: flags drift"
    # full BenchmarkReport (anchors + provenance + totals) exact
    assert report == ak["benchmark_report"], f"{sid}: benchmark_report drift"
    # ask surface exact
    assert scen_gen.build_ask(report) == ak["ask"], f"{sid}: ask drift"


# ── sc01 == the LOCKED demo answer key (Maya through the generalized flow) ──
def test_sc01_reproduces_locked_demo_answer_key():
    locked = _load_seed("demo_answer_key.json")
    ak = _load("sc01_maya_baseline", "answer_key.json")

    # flag dollar-impacts, keyed (engine-type, code) — nsa contract name folded back
    def _key(t):
        return "nsa" if t == "nsa_balance_billing" else t
    got = {(_key(f["type"]), f.get("code")): f["dollar_impact"] for f in ak["expected_flags"]}
    for lf in locked["seeded_flags"]:
        assert got[(lf["type"], lf.get("cpt"))] == lf["dollar_impact"], f"locked {lf['type']} drift"

    # the case-level locked totals reproduce through the fixture spec
    bill = DEMO_JOB_SPEC["bill"]
    assert bill["total_billed"] == locked["case"]["total_billed"] == 8432.0
    assert bill["patient_balance"] == locked["case"]["patient_balance"] == 4287.0
    assert (DEMO_JOB_SPEC["eob"]["patient_responsibility_total"]
            == locked["case"]["eob_patient_responsibility"] == 3875.0)


def test_sc01_flags_equal_the_engine_demo_flags(config, lookup, ncci):
    """The four sc01 flags are exactly what the engine computes on the fixture
    JobSpec — i.e. app.fixtures.demo_flags(), the app's canonical demo path."""
    ak = _load("sc01_maya_baseline", "answer_key.json")
    engine = scen_gen.serialize_flags(demo_flags())
    assert engine == ak["expected_flags"]


# ── zero-error-flag (clean) scenarios ──────────────────────────────────────
@pytest.mark.parametrize("sid", ["sc05_self_pay_gross", "sc08_clean_overpriced"])
def test_clean_scenarios_have_zero_error_flags(sid, lookup, config, ncci):
    ak = _load(sid, "answer_key.json")
    assert ak["expected_flags"] == []
    js = JobSpec.model_validate(_load(sid, "job_spec.json"))
    assert detect_flags(js, config, demo_benchmarks(), ncci, lookup=lookup) == []
    # still a benchmarking case: at least one line is flagged above the RAND norm
    assert any(ln["rand_flag"] for ln in ak["benchmark_report"]["lines"]), \
        f"{sid} should have RAND-flagged lines"


# ── every answer-key number traces to the lookup/config, none invented ─────
def test_byte_stable_regeneration():
    assert scen_gen.generate(check=True) == 0, "committed artifacts drifted from the generator"


# ── /scenarios endpoints round-trip ────────────────────────────────────────
@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_scenarios_endpoint_lists_all_nine(client):
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    listed = {s["scenario_id"] for s in resp.json()["scenarios"]}
    assert set(SCENARIO_IDS) <= listed
    assert len([s for s in resp.json()["scenarios"] if s["scenario_id"] in SCENARIO_IDS]) == 9


@pytest.mark.parametrize("sid", SCENARIO_IDS)
def test_load_scenario_stores_the_answer_keys_numbers(client, sid):
    ak = _load(sid, "answer_key.json")
    resp = client.post(f"/scenarios/{sid}/load")
    assert resp.status_code == 200
    case_id = resp.json()["case_id"]

    # the case carries the committed answer key + benchmark report verbatim
    assert case_store.get(case_id, "answer_key") == ak
    assert case_store.get(case_id, "benchmark_report") == ak["benchmark_report"]

    allowed = {round(float(x), 2) for x in case_store.get(case_id, "allowed_numbers")}
    for f in ak["expected_flags"]:
        if f.get("dollar_impact") is not None:
            assert round(f["dollar_impact"], 2) in allowed, f"{sid}: flag impact not citable"
    # the report's headline ask numbers are citable too
    for key in ("ask_anchor", "ask_target", "floor"):
        v = ak["benchmark_report"]["totals"].get(key)
        if isinstance(v, (int, float)):
            assert round(float(v), 2) in allowed

    # mappable flags surface on the case (type + impact preserved)
    served = client.get(f"/cases/{case_id}/flags").json()["flags"]
    served_impacts = {round(f["dollar_impact"], 2) for f in served}
    for f in ak["expected_flags"]:
        if f.get("dollar_impact"):
            assert round(f["dollar_impact"], 2) in served_impacts, f"{sid}: {f['type']} not served"


# ── simulated-call honesty invariant (pre-call) ────────────────────────────
@pytest.mark.parametrize("sid", FLAG_SCENARIO_IDS)
def test_simulated_call_speaks_only_citable_numbers(client, sid, config):
    """Load the scenario, build the case-generic call sequence, and assert every
    dollar figure the agent speaks is citable: it is either in the case's
    answer-key allowed set (case data + expected flags + benchmark anchors) or a
    benchmark-dossier figure the engine derived. Nothing is invented."""
    ak = _load(sid, "answer_key.json")
    case_id = client.post(f"/scenarios/{sid}/load").json()["case_id"]
    allowed = {round(float(x), 2) for x in case_store.get(case_id, "allowed_numbers")}

    # the sim also voices its engine-built dossier's anchor/target/floor (built
    # over the benchmark seed) — those are grounded, not invented; include them.
    spec = JobSpec.model_validate(case_store.get_job_spec(case_id))
    flags = detect_flags(spec, config, demo_benchmarks(), lookup=None)
    dossier = build_dossier(spec, flags, demo_benchmarks(), config, entity=spec.entities[0])
    grounded = allowed | {round(dossier.anchor, 2), round(dossier.target, 2),
                          round(dossier.floor, 2), 0.0}

    steps = build_generic_sequence("00000000-0000-0000-0000-0000000000aa", case_id)
    spoken: list[float] = []
    for s in steps:
        if s["kind"] == "event" and s["type"] == "transcript" and s["payload"]["speaker"] == "agent":
            for m in _DOLLAR_RE.finditer(s["payload"]["text"]):
                spoken.append(round(float(m.group(1).replace(",", "")), 2))

    uncited = [n for n in spoken if not any(abs(n - a) <= 1.0 for a in grounded)]
    assert not uncited, f"{sid}: simulator spoke uncitable numbers {uncited}"

    # tight link: the top flag the agent cites comes straight from the answer key
    if flags:
        top = max(flags, key=lambda f: f.dollar_impact)
        assert round(top.dollar_impact, 2) in allowed, \
            f"{sid}: top flag impact not in the answer-key allowed set"


def _load_seed(name: str) -> dict:
    with open(REPO_ROOT / "data" / "seed" / name, encoding="utf-8") as f:
        return json.load(f)
