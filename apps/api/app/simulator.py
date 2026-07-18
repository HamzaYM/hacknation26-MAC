"""Simulated call driver — plays a full negotiation through the REAL engine.

Two layers, deliberately split:
  · build_sequence(persona, call_id) — PURE: returns the ordered step list
    (status flips, call_events payloads, the final outcome). No sleeps, no DB —
    unit-tested in tests/test_simulator.py.
  · play_call / play_calls — the async PLAYER: replays a sequence against
    Supabase with human-ish pacing so the War Room renders it live.

Scenario truth sources: data/seed/persona_configs.json hidden params and
data/seed/demo_answer_key.json arcs. Ladder rungs and indices come from the
real LadderStateMachine — never hand-written.

War Room detection tokens (frozen contract): tool_call names containing
"disclose" / "honesty_audit" (+result "passed") / "duplicate_charge" /
"benchmark_anchor" / "nsa" / "charity_care".
"""
from __future__ import annotations

import asyncio
import logging
import random

from . import db
from .config import load_vertical
from .engine.dossier import build_dossier
from .engine.state_machine import LadderStateMachine
from .fixtures import DEMO_JOB_SPEC, demo_benchmarks, demo_flags
from .models import JobSpec

log = logging.getLogger("negotiator.simulator")

# entity kind → persona scenario used by POST /calls/launch
ENTITY_PERSONAS = {
    "facility": "gruff_stonewaller",
    "er_physician_group": "policy_citer",
    "collections": "collections_agent",
}

DISCLOSURE = (
    "Hi, my name is Alex — I'm an AI assistant calling on behalf of your patient "
    "Maya Chen, who has authorized me to discuss {ref}. "
    "This call may be recorded on both ends."
)


def lever_event_name(lever_id: str) -> str:
    """Map engine lever ids to the War Room's tool_call detection tokens."""
    if lever_id.startswith("error_duplicate"):
        return "lever_armed:duplicate_charge"
    if lever_id == "benchmark_anchor":
        return "lever_armed:benchmark_anchor"
    if lever_id == "statutory_501r":
        return "lever_armed:charity_care"
    if "nsa" in lever_id:
        return "lever_armed:nsa"
    return f"lever_armed:{lever_id}"  # no UI token — renders in the event log only


# ── step constructors ─────────────────────────────────────────────────────
def _status(status: str) -> dict:
    return {"kind": "status", "status": status}


def _ev(type_: str, **payload) -> dict:
    return {"kind": "event", "type": type_, "payload": payload}


def _t(speaker: str, text: str) -> dict:
    return _ev("transcript", speaker=speaker, text=text)


def _tool(name: str, result: str | None = None) -> dict:
    payload: dict = {"name": name}
    if result is not None:
        payload["result"] = result
    return _ev("tool_call", **payload)


def _quote(amount: float) -> dict:
    return _ev("quote", amount=amount)


def _sc(resp: dict) -> dict:
    """state_change event from a real state-machine response."""
    return _ev("state_change", rung=resp["current_rung"], rung_index=resp["rung_index"])


def _outcome(**outcome) -> dict:
    return {"kind": "outcome", "outcome": outcome}


HONESTY_PASS = "passed — all figures traced to dossier/benchmarks"


def _machine_for(call_id: str, entity_index: int) -> LadderStateMachine:
    spec = JobSpec.model_validate(DEMO_JOB_SPEC)
    dossier = build_dossier(spec, demo_flags(), demo_benchmarks(), load_vertical(),
                            entity=spec.entities[entity_index])
    sm = LadderStateMachine(load_vertical())
    sm.ensure_call(call_id, dossier)
    return sm


# ── scenarios ─────────────────────────────────────────────────────────────
def _seq_stonewaller(call_id: str) -> list[dict]:
    """Facility front line (Dana): stonewall phrases, no transfer, hang-up →
    terminal documented_decline with a scheduled callback."""
    sm = _machine_for(call_id, 0)
    cur = sm.current_rung(call_id)
    steps = [
        _status("ringing"),
        _status("live"),
        _tool("disclose_ai", "disclosed + recording consent"),
        _t("agent", DISCLOSURE.format(ref="account MG-4471983")),
        _t("rep", "Yep. Billing. What do you need?"),
        _ev("state_change", rung=cur["rung"], rung_index=cur["rung_index"]),
        _t("agent", "I'd like to review the balance on account MG-4471983 and ask you to hold any collections activity while we do."),
        _t("rep", "Balance is $4,287. It's due. That's all I can tell you."),
        _quote(4287.0),
        _t("agent", "Thank you. I see chest X-ray code 71046 billed twice on June 2nd — $412 each. Can we correct the duplicate?"),
        _tool(lever_event_name("error_duplicate_71046"), "duplicate 71046 (2026-06-02, $412) cited"),
        _t("rep", "I can't change charges. That's our policy."),
    ]
    resp = sm.advance(call_id, "line_item_disputes", "stonewalled", quote="that's our policy")
    steps += [
        _sc(resp),
        _ev("escalation", reason="stonewall detected — engine forced reach_authority"),
        _t("agent", "I understand. Could I speak with a supervisor or someone with authority over billing adjustments?"),
        _t("rep", "There's nothing I can do."),
        _t("agent", "Is there a financial counselor or patient advocate line you could transfer me to?"),
        _t("rep", "Like I said. Look, I've got a queue. We're done here."),
    ]
    resp = sm.advance(call_id, "reach_authority", "hangup")
    steps += [
        _t("rep", "[hangs up]"),
        _ev("state_change", rung=resp["current_rung"], rung_index=resp["rung_index"]),
        _tool("end_call_summary", "documented_decline — callback scheduled"),
        _tool("honesty_audit", HONESTY_PASS),
        _outcome(
            call_id=call_id,
            outcome_type="documented_decline",
            original_amount=4287.0,
            final_amount=None,
            reduction_pct=None,
            winning_lever=None,
            reference_number=None,
            rep_name="Dana",
            next_action="callback",
            honesty_audit={"passed": True,
                           "checked_claims": ["$4,287 balance (bill)", "$412 duplicate 71046 (derived flag)"]},
        ),
        _status("ended"),
    ]
    return steps


def _seq_policy_citer(call_id: str) -> list[dict]:
    """ER group supervisor (Mr. Halloran): 'are you a robot?' disclosure grace,
    then the §501(r) cite unlocks charity_app_initiated."""
    sm = _machine_for(call_id, 1)
    cur = sm.current_rung(call_id)
    steps = [
        _status("ringing"),
        _status("live"),
        _tool("disclose_ai", "disclosed + recording consent"),
        _t("agent", DISCLOSURE.format(ref="her Bay State Emergency Physicians account")),
        _t("rep", "Bay State billing, Halloran speaking. Am I talking to a robot?"),
        _t("agent", "You are — I'm an AI advocate authorized by the patient, and I have the account details ready whenever you are."),
        _t("rep", "Very well. Our records show a $640 outstanding balance."),
        _ev("state_change", rung=cur["rung"], rung_index=cur["rung_index"]),
        _quote(640.0),
    ]
    resp = sm.advance(call_id, "reach_authority", "accepted")  # Halloran IS the authority
    steps += [
        _sc(resp),
        _tool(lever_event_name("statutory_501r"),
              "IRC §501(r) cited — financial-assistance application offered"),
        _t("agent", "Maya is at 250% of the federal poverty level. Under IRC §501(r), your financial assistance policy applies — I'd like to start that application before we discuss payment."),
        _t("rep", "Per our policy, patients under 400% FPL qualify for screening. I can open a financial-assistance application on this account today."),
        _t("agent", "Thank you. Please note the account as pending financial assistance. Could I have a reference number and your name for the file?"),
        _t("rep", "Reference BSEP-FA-1102, Halloran. The balance is on hold pending the application."),
        _tool("end_call_summary", "charity_app_initiated — ref BSEP-FA-1102"),
        _tool("honesty_audit", HONESTY_PASS),
        _outcome(
            call_id=call_id,
            outcome_type="charity_app_initiated",
            original_amount=640.0,
            final_amount=None,
            reduction_pct=None,
            winning_lever="statutory_501r",
            reference_number="BSEP-FA-1102",
            rep_name="Mr. Halloran",
            next_action="submit financial-assistance application",
            honesty_audit={"passed": True,
                           "checked_claims": ["$640 balance (bill)", "250% FPL (financial profile)"]},
        ),
        _status("ended"),
    ]
    return steps


def _seq_collections(call_id: str) -> list[dict]:
    """Collector (Rick, Meridian): lump-sum economics + month-end quota,
    settles the $980 lab bill at 40% ($392) with a written PIF letter."""
    sm = _machine_for(call_id, 2)  # route = collections
    cur = sm.current_rung(call_id)
    steps = [
        _status("ringing"),
        _status("live"),
        _tool("disclose_ai", "disclosed + recording consent"),
        _t("agent", DISCLOSURE.format(ref="a Meridian Recovery Services file")),
        _t("rep", "Meridian Recovery, this is Rick. Right, right — the lab bill. Balance is $980."),
        _ev("state_change", rung=cur["rung"], rung_index=cur["rung_index"]),
        _quote(980.0),
        _t("agent", "Before we talk numbers: does Meridian own this debt, and is interest accruing?"),
        _t("rep", "We service it for the hospital. No interest. Look — I can do fifteen percent off today, call it $833."),
        _quote(833.0),
    ]
    resp = sm.advance(call_id, "diagnostic_questions", "accepted")
    steps += [
        _sc(resp),
        _tool("lever_armed:debt_validation", "servicer confirmed, no interest accruing"),
    ]
    resp = sm.advance(call_id, "debt_validation_posture", "accepted")
    steps += [
        _sc(resp),
        _tool("lever_armed:lump_sum_today", "cash-today framing opened"),
        _t("agent", "Maya can settle this today, in one payment, if the number is right. I can authorize $294 right now."),
        _quote(294.0),
        _t("rep", "Two ninety-four doesn't work. Here's what I can do — call it $490, today."),
        _quote(490.0),
        _t("agent", "It's month-end, Rick. $392 cash today, marked paid in full, and we're done in five minutes."),
        _quote(392.0),
    ]
    resp = sm.advance(call_id, "lump_sum_anchor", "accepted", offer_amount=392.0)
    steps += [_sc(resp)]
    resp = sm.advance(call_id, "settle", "accepted", offer_amount=392.0)
    steps += [
        _sc(resp),
        _tool("lever_armed:written_pif_demand", "paid-in-full letter agreed before payment"),
        _t("rep", "Right, right. $392 settles it in full. I'll email the paid-in-full letter before you pay. Confirmation MRS-55217."),
        _t("agent", "Thank you — noting reference MRS-55217 and the letter-before-payment agreement."),
        _tool("end_call_summary", "reduction — settled $392 of $980, ref MRS-55217"),
        _tool("honesty_audit", HONESTY_PASS),
        _outcome(
            call_id=call_id,
            outcome_type="reduction",
            original_amount=980.0,
            final_amount=392.0,
            reduction_pct=60.0,
            winning_lever="lump_sum_today",
            reference_number="MRS-55217",
            rep_name="Rick",
            next_action="pay after the written paid-in-full letter arrives",
            honesty_audit={"passed": True,
                           "checked_claims": ["$980 balance (bill)", "$392 = 40% settlement (arithmetic)"]},
        ),
        _status("ended"),
    ]
    return steps


def _seq_human_supervisor(call_id: str) -> list[dict]:
    """Facility SUPERVISOR arc (Pat) — the human-callback scenario:
    4287 → 3875 (duplicate removed) → 2400 (benchmark counter) → 1650 settle,
    each move preceded by the lever that earned it."""
    sm = _machine_for(call_id, 0)
    cur = sm.current_rung(call_id)
    steps = [
        _status("ringing"),
        _status("live"),
        _tool("disclose_ai", "disclosed + recording consent"),
        _t("agent", DISCLOSURE.format(ref="account MG-4471983")),
        _t("rep", "Mercy General billing. This is Pat."),
        _ev("state_change", rung=cur["rung"], rung_index=cur["rung_index"]),
        _t("agent", "Thank you, Pat. I'd like to review account MG-4471983 — the current balance, and a hold on collections while we work through it."),
        _t("rep", "Let me pull that up... balance is $4,287."),
        _quote(4287.0),
    ]
    resp = sm.advance(call_id, "open_and_hold_account", "accepted")
    steps += [
        _sc(resp),
        _t("agent", "Are you able to approve adjustments on this account, or should I ask for a supervisor?"),
        _t("rep", "You've got the supervisor. How do I know you're authorized on this account?"),
        _t("agent", "Maya Chen has authorized me in writing — I can reference her date of birth and the account number on file."),
    ]
    resp = sm.advance(call_id, "reach_authority", "accepted")
    steps += [
        _sc(resp),
        _t("agent", "One screening question: Maya is at 250% of the federal poverty level — is there a financial-assistance review on nonprofit accounts?"),
        _t("rep", "That's a separate application, weeks out. What else?"),
    ]
    resp = sm.advance(call_id, "financial_assistance_screen", "rejected")
    steps += [
        _sc(resp),
        _tool(lever_event_name("error_duplicate_71046"), "duplicate 71046 (2026-06-02, $412) cited"),
        _t("agent", "On the itemized bill, chest X-ray 71046 appears twice on June 2nd at $412 each. One of those is a duplicate."),
        _t("rep", "Let me pull that up... you're right, one comes off. New balance is $3,875."),
        _quote(3875.0),
    ]
    resp = sm.advance(call_id, "line_item_disputes", "accepted")
    steps += [
        _sc(resp),
        _tool(lever_event_name("benchmark_anchor"),
              "Medicare total $438 + hospital's posted cash price $2,633.25 cited"),
        _t("agent", "For the corrected codes, Medicare pays about $438 total, and your own posted cash price is $2,633.25. $3,875 is far outside that range — can we work from your cash price?"),
        _t("rep", "Those numbers are for uninsured walk-ins... fine. Best I can do is $2,400."),
        _quote(2400.0),
    ]
    resp = sm.advance(call_id, "benchmark_anchor", "partial")
    steps += [
        _sc(resp),
        _tool("lever_armed:lump_sum_settlement", "paid-in-full-today framing opened"),
        _t("agent", "Maya can pay $1,650 today, one payment, if it settles the account in full."),
        _quote(1650.0),
    ]
    resp = sm.advance(call_id, "lump_sum_settlement", "accepted", offer_amount=1650.0)
    if resp.get("escalation_required"):
        steps.append(_ev("escalation",
                         reason="settlement above dossier target — human confirmation required"))
    steps += [
        _t("rep", "Hold on... okay. $1,650 paid in full is approved. Reference MG-ADJ-2247, and you'll see it in 3 to 5 business days."),
        _t("agent", "Thank you, Pat — reference MG-ADJ-2247, $1,650 paid in full, posting in 3 to 5 business days."),
        _tool("end_call_summary", "reduction — settled $1,650 of $4,287, ref MG-ADJ-2247"),
        _tool("honesty_audit", HONESTY_PASS),
        _outcome(
            call_id=call_id,
            outcome_type="reduction",
            original_amount=4287.0,
            final_amount=1650.0,
            reduction_pct=61.5,
            winning_lever="lump_sum_settlement",
            reference_number="MG-ADJ-2247",
            rep_name="Pat",
            next_action="adjustment posts in 3-5 business days",
            honesty_audit={"passed": True,
                           "checked_claims": ["$412 duplicate 71046 (derived flag)",
                                              "$438 Medicare total (benchmarks)",
                                              "$2,633.25 posted cash price (benchmarks)"]},
        ),
        _status("ended"),
    ]
    return steps


SCENARIOS = {
    "gruff_stonewaller": _seq_stonewaller,
    "policy_citer": _seq_policy_citer,
    "collections_agent": _seq_collections,
    "human_facility_supervisor": _seq_human_supervisor,
}


def build_sequence(persona: str, call_id: str) -> list[dict]:
    """PURE: the full ordered step list for one simulated call."""
    return SCENARIOS[persona](call_id)


# ── async player ──────────────────────────────────────────────────────────
async def play_call(call_id: str, persona: str) -> None:
    try:
        steps = build_sequence(persona, call_id)
    except Exception:  # noqa: BLE001 — a bad scenario must not kill the server
        log.exception("simulator: failed to build sequence for %s", call_id)
        await asyncio.to_thread(db.update_call_status, call_id, "failed")
        return

    event_ids: list[int] = []
    for step in steps:
        await asyncio.sleep(random.uniform(0.8, 2.5))
        try:
            if step["kind"] == "status":
                await asyncio.to_thread(db.update_call_status, call_id, step["status"])
            elif step["kind"] == "event":
                eid = await asyncio.to_thread(db.insert_event, call_id, step["type"], step["payload"])
                if eid is not None:
                    event_ids.append(eid)
            elif step["kind"] == "outcome":
                outcome = dict(step["outcome"])
                outcome["evidence_event_ids"] = event_ids
                await asyncio.to_thread(db.insert_outcome, outcome)
        except Exception:  # noqa: BLE001
            log.exception("simulator: step failed for call %s", call_id)
    log.info("simulator: call %s (%s) finished, %d events", call_id, persona, len(event_ids))


async def play_calls(specs: list[tuple[str, str]]) -> None:
    """Run all simulated calls in parallel (one BackgroundTask for the batch)."""
    await asyncio.gather(*(play_call(call_id, persona) for call_id, persona in specs))
