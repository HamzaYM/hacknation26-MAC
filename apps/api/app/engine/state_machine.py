"""Per-call ladder state machine — the Closer's brain-stem (PRD §8.2).

The voice agent reports what just happened via report_lever_result; THIS
module decides the next move. The LLM never chooses its own escalation.

State is an in-memory dict keyed by call_id — fine for a single uvicorn
worker. TODO(Hamza): persist to Supabase (`calls.rung` + `call_events`
rung_advanced rows) so state survives restarts and multiple workers.

Rules enforced here, not in the prompt:
  · linear advance through config ladder.<route> on accepted/rejected/partial
  · stonewall (result == "stonewalled" OR a config escalation_triggers phrase
    in the reported text) → force the reach_authority rung
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


class LadderStateMachine:
    def __init__(self, config: dict):
        self._config = config
        self._triggers = [t.casefold() for t in config.get("escalation_triggers", [])]
        self._required_questions: dict[str, list[str]] = config.get("required_questions", {})
        self._states: dict[str, CallState] = {}  # in-memory; Supabase later

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
                "current_rung": state.ladder[state.index],
                "rung_index": state.index,
                "notes": "counterparty hung up — log a documented decline and schedule a callback",
            }

        # stonewall → force reach_authority (Goodbill supervisor script)
        text = " ".join(filter(None, [result, quote])).casefold()
        # Normalize unicode curly quotes/apostrophes so triggers match LLM output
        text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
        if result == "stonewalled" or any(t in text for t in self._triggers):
            # Cap forced escalations at 2 per call (live a2a finding: endless
            # "transfer to a supervisor" loop) → close out with a structured decline.
            state.stonewall_escalations += 1
            if state.stonewall_escalations > 2:
                state.index = len(state.ladder) - 1
                return self._respond(state, escalation=True,
                                     notes="escalation limit reached — stop asking for supervisors; "
                                           "capture reference number + rep name, log a documented "
                                           "decline, and schedule a callback")
            if "reach_authority" in state.ladder:
                state.index = state.ladder.index("reach_authority")
                return self._respond(state, escalation=True,
                                     notes="stonewall detected — ask for someone with authority to help")

        # Deterministic anti-repetition guardrail (Hamza, 07-18): the same lever
        # reported with the same non-accepted result 3 times in a row means the
        # point is exhausted — force the next rung instead of letting the agent
        # argue it a fourth time.
        recent = state.history[-3:]
        if (len(recent) == 3 and result != "accepted"
                and all(h["lever"] == lever and h["result"] == result for h in recent)):
            state.index = min(state.index + 1, len(state.ladder) - 1)
            return self._respond(state, repetition_cap=True,
                                 notes="you have made this point three times — drop it, move to "
                                       "the next lever, and do not repeat the previous ask", **q_extra)

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
