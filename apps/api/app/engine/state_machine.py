"""Per-call ladder state machine — the Closer's brain-stem (PRD §8.2).

The voice agent reports what just happened via report_lever_result; THIS
module decides the next move. The LLM never chooses its own escalation.

State is an in-memory dict keyed by call_id — fine for a single uvicorn
worker. TODO(Hamza): persist to Supabase (`calls.rung` + `call_events`
rung_advanced rows) so state survives restarts and multiple workers.

Rules enforced here, not in the prompt:
  · linear advance through config ladder.<route> on accepted/rejected/partial
  · impasse (same lever unhedged-stonewalled twice, OR the same non-accepted
    point made three times) → PARK the topic as an open item and advance to the
    next lever (escalation_policy: last_resort — a bare stonewall no longer jumps
    to a supervisor)
  · reach_authority arms only as a LAST RESORT: when the rep's words say only
    someone with authority can act, or every other lever is attempted/parked and
    material still remains
  · result == "hangup" → terminal documented_decline, next_action = callback
  · floor: any offer above dossier.floor is rejected (rung unchanged)
  · target: settling above dossier.target is allowed only with an explicit
    escalation flag in the response (escalation_required = True)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models import StrategyDossier


@dataclass
class CallState:
    call_id: str
    dossier: StrategyDossier
    ladder: list[str]
    index: int = 0
    stonewall_escalations: int = 0
    terminal: bool = False
    terminal_outcome: str | None = None
    history: list[dict] = field(default_factory=list)
    # Question-coverage memory (tag → answer snippet). Populated as the agent
    # reports questions_asked; the coverage gate reads it before letting the
    # call walk off a required-questions rung.
    questions_covered: dict[str, str] = field(default_factory=dict)
    # The gate only engages once the agent has started reporting questions_asked
    # (real calls do; legacy callers that never send tags stay ungated).
    questions_active: bool = False
    # Rungs already blocked once for coverage — one block max per rung.
    coverage_blocked: set[str] = field(default_factory=set)
    # Parked topics (impasses set aside as open items): [{lever, reason}].
    parked_topics: list[dict] = field(default_factory=list)
    # Unhedged stonewalls seen per lever — a lever parks on the 2nd (impasse).
    lever_stonewalls: dict[str, int] = field(default_factory=dict)
    # Set once the rep's own words say only someone with authority can act —
    # the ONLY per-call signal (besides ladder exhaustion) that arms reach_authority
    # under escalation_policy: last_resort.
    authority_requested: bool = False


class LadderStateMachine:
    def __init__(self, config: dict):
        self._config = config
        self._triggers = [t.casefold() for t in config.get("escalation_triggers", [])]
        self._authority_triggers = [t.casefold() for t in config.get("authority_triggers", [])]
        self._hedge_markers = [t.casefold() for t in config.get("hedge_markers", [])]
        self._last_resort = config.get("escalation_policy") == "last_resort"
        self._required_questions: dict[str, list[str]] = config.get("required_questions", {})
        self._states: dict[str, CallState] = {}  # in-memory; Supabase later

    def parked_topics(self, call_id: str) -> list[dict]:
        """Open items the call set aside (impasses) — read by end_call_summary
        to persist them as scheduled open_items. Empty when the call is unknown."""
        state = self._states.get(call_id)
        return list(state.parked_topics) if state else []

    def ensure_call(self, call_id: str, dossier: StrategyDossier) -> CallState:
        """Create state on first contact; no-op if the call already exists."""
        if call_id not in self._states:
            ladder = self._config["ladder"][dossier.route]
            self._states[call_id] = CallState(call_id=call_id, dossier=dossier, ladder=list(ladder))
        return self._states[call_id]

    def current_rung(self, call_id: str) -> dict:
        """For rung_advanced events / the War Room ladder widget."""
        state = self._states[call_id]
        return {
            "rung": state.ladder[state.index],
            "rung_index": state.index,
            "terminal": state.terminal,
            "outcome_type": state.terminal_outcome,
        }

    def _exhausted(self, state: CallState) -> bool:
        """True when every non-escalation, non-terminal lever has been attempted or
        parked AND at least one parked topic still needs resolution — condition (a)
        for arming reach_authority under escalation_policy: last_resort."""
        if not state.parked_topics:  # nothing material still open
            return False
        covered = ({h["lever"] for h in state.history}
                   | {p["lever"] for p in state.parked_topics})
        terminal_rung = state.ladder[-1]
        pending = [r for r in state.ladder
                   if r not in ("reach_authority", terminal_rung) and r not in covered]
        return not pending

    def advance(
        self,
        call_id: str,
        lever: str,
        result: str,
        offer_amount: float | None = None,
        quote: str | None = None,
        questions_asked: list[str] | None = None,
    ) -> dict:
        state = self._states[call_id]
        qa = list(questions_asked or [])
        state.history.append({"lever": lever, "result": result,
                              "offer_amount": offer_amount, "questions_asked": qa})
        dossier = state.dossier

        # Question memory + notifications (A2 already-asked, A3 repeat cap).
        # already-asked is computed BEFORE we union the current tags in.
        q_extra: dict = {}
        already = [t for t in qa if t in state.questions_covered]
        if already:
            q_extra["already_asked"] = already
        for t in qa:
            state.questions_covered.setdefault(t, quote or "")
        if qa:
            state.questions_active = True
        if qa and len(state.history) >= 3:
            last3 = state.history[-3:]
            repeated = [t for t in qa if all(t in h.get("questions_asked", []) for h in last3)]
            if repeated:
                q_extra["question_repeat_cap"] = repeated

        if state.terminal:
            return self._respond(state, move_allowed=False,
                                 notes=f"call is terminal ({state.terminal_outcome}); no further moves")

        # floor: the agent may never offer more than the patient can pay
        if offer_amount is not None and offer_amount > dossier.floor:
            return self._respond(state, move_allowed=False,
                                 notes=f"rejected: offer ${offer_amount:.2f} exceeds floor "
                                       f"${dossier.floor:.2f} — never offer above the floor")

        # hang-up → documented decline with a scheduled callback (C4)
        if result == "hangup":
            state.terminal = True
            state.terminal_outcome = "documented_decline"
            return {
                "next_move": "documented_decline",
                "move_allowed": True,
                "terminal": True,
                "outcome_type": "documented_decline",
                "next_action": "callback",
                "end_call_now": True,
                "current_rung": state.ladder[state.index],
                "rung_index": state.index,
                "notes": "counterparty hung up — log a documented decline and schedule a callback",
            }

        # Classify the rep's words: normalize unicode curly quotes first so
        # triggers match LLM output, then read stonewall / authority / hedge signals.
        text = " ".join(filter(None, [result, quote])).casefold()
        text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
        is_stonewall = result == "stonewalled" or any(t in text for t in self._triggers)
        # The rep's own words say only someone with authority can act — the one
        # per-call signal (besides ladder exhaustion) that arms reach_authority.
        authority_quote = any(t in text for t in self._authority_triggers)
        # A hedged/temporary refusal ("right now", "I don't have the authority") is
        # not a hard impasse: it must NOT count toward parking. Authority quotes are
        # hedged in this sense (they defer to a supervisor, they don't refuse forever).
        hedged = authority_quote or any(m in text for m in self._hedge_markers)
        if authority_quote:
            state.authority_requested = True
        if is_stonewall and not hedged:
            state.lever_stonewalls[lever] = state.lever_stonewalls.get(lever, 0) + 1

        def _to_reach_authority(reason: str) -> dict:
            # Cap forced escalations at 2 per call (live a2a finding: endless
            # "transfer to a supervisor" loop) → close out with a structured decline.
            state.stonewall_escalations += 1
            if state.stonewall_escalations > 2:
                state.index = len(state.ladder) - 1
                return self._respond(state, escalation=True,
                                     notes="escalation limit reached — stop asking for supervisors; "
                                           "capture reference number + rep name, log a documented "
                                           "decline, and schedule a callback", **q_extra)
            state.index = state.ladder.index("reach_authority")
            return self._respond(state, escalation=True, notes=reason, **q_extra)

        if self._last_resort:
            # Escalation is a LAST RESORT (config escalation_policy: last_resort): a
            # bare stonewall no longer jumps to a supervisor — it parks (below).
            # reach_authority arms ONLY when (b) the rep says only authority can act,
            # or (a) every other lever is attempted/parked and material still remains.
            arm = state.authority_requested or self._exhausted(state)
            if "reach_authority" in state.ladder and lever != "reach_authority" and arm:
                if state.authority_requested:
                    reason = "rep says only someone with authority can act — escalate now"
                    state.authority_requested = False  # consumed; re-arm on a fresh authority quote
                else:
                    reason = ("every other lever is attempted or parked and something material "
                              "remains — escalate to someone with authority as the last resort")
                return _to_reach_authority(reason)
        elif is_stonewall and "reach_authority" in state.ladder:
            # Legacy policy (verticals without escalation_policy: last_resort):
            # a stonewall forces reach_authority immediately.
            return _to_reach_authority("stonewall detected — ask for someone with authority to help")

        # Park the topic on an impasse and move on (Hamza, 07-18: park, don't
        # escalate). Impasse = the same lever unhedged-stonewalled twice, OR the same
        # non-accepted point made three times in a row. Set it aside as an open item,
        # advance to the next lever, and let end_call_summary schedule the follow-up.
        recent = state.history[-3:]
        impasse_repetition = (len(recent) == 3 and result != "accepted"
                              and all(h["lever"] == lever and h["result"] == result for h in recent))
        impasse_stonewall = (is_stonewall and not hedged
                             and state.lever_stonewalls.get(lever, 0) >= 2)
        if impasse_repetition or impasse_stonewall:
            if lever in state.ladder:
                state.index = state.ladder.index(lever)
            state.index = min(state.index + 1, len(state.ladder) - 1)
            reason = ("stonewalled twice on the same point — unhedged refusal"
                      if impasse_stonewall else "made this same point three times")
            parked = {"lever": lever, "reason": reason}
            state.parked_topics.append(parked)
            return self._respond(
                state, parked=parked,
                notes="set this aside as an open item, tell the rep you'll follow up separately, "
                      "and move on — e.g. \"Okay, let's set that one aside for now, I'll chase it "
                      "separately.\"", **q_extra)

        # Question-coverage gate (A1): don't let the call walk OFF a rung that
        # has required questions until they're covered. One block max per rung
        # (never hard-deadlock a live call); on the second pass allow the move
        # but flag the gap so tools.py can log a coverage_gap event.
        required = self._required_questions.get(lever, [])
        if state.questions_active and required:
            missing = [t for t in required if t not in state.questions_covered]
            if missing and lever not in state.coverage_blocked:
                state.coverage_blocked.add(lever)
                if lever in state.ladder:
                    state.index = state.ladder.index(lever)  # stay on this rung
                plain = ", ".join(t.replace("_", " ") for t in missing)
                return self._respond(state, move_allowed=False,
                                     notes=f"before moving on, cover: {plain}", **q_extra)
            if missing:
                q_extra["coverage_incomplete"] = missing

        # linear advance from the reported rung (clamped at the last rung)
        if lever in state.ladder:
            state.index = state.ladder.index(lever)
        state.index = min(state.index + 1, len(state.ladder) - 1)

        note_parts: list[str] = []
        extra: dict = dict(q_extra)
        if offer_amount is not None and offer_amount > dossier.target:
            extra["escalation_required"] = True
            note_parts.append(f"above target ${dossier.target:.2f} — settling at "
                              f"${offer_amount:.2f} requires an escalation flag")
        if extra.get("coverage_incomplete"):
            note_parts.append("coverage still incomplete — the gap is logged; "
                              "don't re-litigate, keep moving")
        if extra.get("already_asked"):
            note_parts.append("already asked and answered — reference the earlier "
                              "answer, don't re-ask")
        if extra.get("question_repeat_cap"):
            note_parts.append("you've asked this three times — log it unresolved and move on")
        notes = " · ".join(note_parts) if note_parts else "advance"
        return self._respond(state, notes=notes, **extra)

    def _respond(self, state: CallState, move_allowed: bool = True, escalation: bool = False,
                 notes: str = "", **extra) -> dict:
        resp = {
            "next_move": state.ladder[state.index],
            "move_allowed": move_allowed,
            "terminal": state.terminal,
            "current_rung": state.ladder[state.index],
            "rung_index": state.index,
            "notes": notes,
        }
        if escalation:
            resp["escalation"] = True
        resp.update(extra)
        return resp
