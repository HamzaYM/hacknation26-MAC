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
    terminal: bool = False
    terminal_outcome: str | None = None
    history: list[dict] = field(default_factory=list)


class LadderStateMachine:
    def __init__(self, config: dict):
        self._config = config
        self._triggers = [t.casefold() for t in config.get("escalation_triggers", [])]
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
    ) -> dict:
        state = self._states[call_id]
        state.history.append({"lever": lever, "result": result, "offer_amount": offer_amount})
        dossier = state.dossier

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
        if result == "stonewalled" or any(t in text for t in self._triggers):
            if "reach_authority" in state.ladder:
                state.index = state.ladder.index("reach_authority")
                return self._respond(state, escalation=True,
                                     notes="stonewall detected — ask for someone with authority to help")

        # linear advance from the reported rung (clamped at the last rung)
        if lever in state.ladder:
            state.index = state.ladder.index(lever)
        state.index = min(state.index + 1, len(state.ladder) - 1)

        notes = "advance"
        extra: dict = {}
        if offer_amount is not None and offer_amount > dossier.target:
            extra["escalation_required"] = True
            notes = (f"above target ${dossier.target:.2f} — settling at ${offer_amount:.2f} "
                     "requires an escalation flag")
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
