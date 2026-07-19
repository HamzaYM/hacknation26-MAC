"""Dan's and Nina's fixture cases through the real engine (app/fixtures_users.py).

Dan (collections): duplicate 71046 $380 + markup 96374 $258.25, route
"collections", anchor/target from the same benchmark math as Maya (Medicare
total $438 → 657/876), floor = his $900 lump sum.

Nina (NSA): the engine now DETECTS the nsa flag ($3,120 billed − $850 in-network
share = $2,270) from her spec — an out-of-network ancillary (anesthesia) provider
above the in-network cost share (config red_flags.nsa). The seeded flag stays as
the expected-answer key; the engine's output must match it. Her story rides config
thresholds.nsa_do_not_negotiate (cite the statute, file a complaint).
"""
import copy

import pytest

from app.config import load_vertical
from app.engine.dossier import build_dossier
from app.engine.flags import detect_flags
from app.fixtures import DEMO_JOB_SPEC, demo_benchmarks
from app.fixtures_users import (
    DAN_EMAIL,
    DAN_JOB_SPEC,
    NINA_EMAIL,
    NINA_JOB_SPEC,
    spec_for_case,
    spec_for_email,
)
from app.models import JobSpec


@pytest.fixture(scope="module")
def dan_spec() -> JobSpec:
    return JobSpec.model_validate(DAN_JOB_SPEC)


@pytest.fixture(scope="module")
def nina_spec() -> JobSpec:
    return JobSpec.model_validate(NINA_JOB_SPEC)


@pytest.fixture(scope="module")
def dan_flags(dan_spec):
    return detect_flags(dan_spec, load_vertical(), demo_benchmarks())


@pytest.fixture(scope="module")
def nina_flags(nina_spec):
    return detect_flags(nina_spec, load_vertical(), demo_benchmarks())


# ── Dan — collections-only, duplicate + markup ────────────────────────────
def test_dan_bill_lines_sum_to_balance(dan_spec):
    total = round(sum(li.billed_amount for li in dan_spec.bill.line_items), 2)
    assert total == dan_spec.bill.total_billed == dan_spec.bill.patient_balance == 2140.00


def test_dan_engine_finds_exactly_duplicate_and_markup(dan_flags):
    assert [(f.type, f.cpt) for f in dan_flags] == [("duplicate", "71046"), ("markup", "96374")]
    by_type = {f.type: f for f in dan_flags}
    assert by_type["duplicate"].dollar_impact == 380.00       # 2nd $380 X-ray line
    assert by_type["markup"].dollar_impact == 258.25          # 520 − band_high 261.75


def test_dan_seeded_flags_match_engine_output(dan_spec, dan_flags):
    seeded = {(f.type, f.cpt): f.dollar_impact for f in dan_spec.derived_flags}
    computed = {(f.type, f.cpt): f.dollar_impact for f in dan_flags}
    assert seeded == computed


def test_dan_dossier_routes_to_collections(dan_spec, dan_flags):
    dossier = build_dossier(dan_spec, dan_flags, demo_benchmarks(), load_vertical(),
                            entity=dan_spec.entities[0])
    assert dossier.route == "collections"
    assert dossier.target_entity == "Meridian Recovery Services"
    # same corrected-CPT benchmark math as Maya's case: Medicare total $438
    assert (dossier.anchor, dossier.target, dossier.floor) == (657.00, 876.00, 900.00)
    assert dossier.anchor <= dossier.target <= dossier.floor
    lever_ids = [l.id for l in dossier.levers]
    assert "error_duplicate_71046" in lever_ids
    assert "statutory_501r" not in lever_ids                  # for-profit facility


# ── Nina — NSA balance bill ───────────────────────────────────────────────
def test_nina_engine_detects_nsa_and_eob_mismatch(nina_flags):
    by = {(f.type, f.cpt): f for f in nina_flags}
    assert set(by) == {("nsa", "00840"), ("eob_mismatch", None)}
    assert by[("nsa", "00840")].dollar_impact == 2270.00          # 3120 billed − 850 in-network share
    assert by[("eob_mismatch", None)].dollar_impact == 2270.00    # 3120 − 850
    assert by[("eob_mismatch", None)].evidence == {"bill": 3120.00, "eob": 850.00}


def test_nina_engine_nsa_matches_the_seeded_answer_key(nina_spec, nina_flags):
    """The seeded flag is the expected-answer key; the ENGINE must reproduce it."""
    seeded = next(f for f in nina_spec.derived_flags if f.type == "nsa")
    engine = next(f for f in nina_flags if f.type == "nsa")
    assert (engine.type, engine.cpt, engine.dollar_impact) == \
        (seeded.type, seeded.cpt, seeded.dollar_impact)
    assert engine.evidence == seeded.evidence


def test_nina_nsa_flag_is_seeded_and_config_says_do_not_negotiate(nina_spec):
    nsa = next(f for f in nina_spec.derived_flags if f.type == "nsa")
    assert nsa.dollar_impact == 2270.00
    assert nsa.evidence["provider_network_status"] == "out_of_network"
    # her path is the config threshold, not a negotiation ladder
    threshold = load_vertical()["thresholds"]["nsa_do_not_negotiate"]
    assert threshold["action"] == "cite_statute_and_file_complaint"


# ── NSA detection matrix (Finding 2) ──────────────────────────────────────
def test_maya_case_emits_no_nsa_flag():
    """Maya has an er_physician_group entity (an ancillary kind) but no
    out-of-network line, so the NSA rule must NOT fire on her case."""
    from app.fixtures import demo_flags
    assert not any(f.type == "nsa" for f in demo_flags())


def test_nsa_below_threshold_does_not_fire():
    """An OON ancillary provider whose balance barely exceeds the in-network
    share (delta < min_impact) is not a protected surprise bill."""
    spec = copy.deepcopy(NINA_JOB_SPEC)
    spec["bill"]["patient_balance"] = 910.00                  # $60 over the $850 in-network share
    spec["eob"]["patient_responsibility_total"] = 850.00
    spec["entities"][1]["balance"] = 910.00
    flags = detect_flags(JobSpec.model_validate(spec), load_vertical(), demo_benchmarks())
    assert not any(f.type == "nsa" for f in flags)            # $60 < min_impact $100


def test_nina_dossier_arms_nsa_lever_first_then_builds_cleanly(nina_spec, nina_flags):
    entity = next(e for e in nina_spec.entities if e.kind == "anesthesia")
    dossier = build_dossier(nina_spec, nina_flags, demo_benchmarks(), load_vertical(), entity=entity)
    assert dossier.route == "provider"
    assert dossier.target_entity == "Commonwealth Anesthesia Associates"
    # NSA statute lever is armed FIRST (cite, don't negotiate — no ladder rung)
    assert dossier.levers[0].id == "statutory_nsa"
    assert dossier.levers[0].armed and dossier.levers[0].dollar_ask == 2270.00
    assert "No Surprises Act" in (dossier.levers[0].citation or "")
    lever_ids = [l.id for l in dossier.levers]
    assert "statutory_501r" in lever_ids                      # nonprofit + fpl 320 ≤ 400
    assert "error_eob_mismatch" in lever_ids
    assert "benchmark_anchor" not in lever_ids                # no benchmark rows for 00840
    assert dossier.floor == 800.00


# ── registry ──────────────────────────────────────────────────────────────
def test_registry_resolves_emails_and_case_ids():
    assert spec_for_email("maya@hagglfor.me") is DEMO_JOB_SPEC
    assert spec_for_email(DAN_EMAIL) is DAN_JOB_SPEC
    assert spec_for_email("NINA@hagglfor.me") is NINA_JOB_SPEC   # case-insensitive
    assert spec_for_email("stranger@example.com") is None
    assert spec_for_case("demo") is DEMO_JOB_SPEC
    assert spec_for_case(DAN_JOB_SPEC["case_id"]) is DAN_JOB_SPEC
    assert spec_for_case(NINA_JOB_SPEC["case_id"]) is NINA_JOB_SPEC
