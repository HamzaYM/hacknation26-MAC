"""Caller endpoints — launch and inspect calls.

Launch flow (PRD §6): build dossier (code) → compile negotiator prompt →
ElevenLabs outbound-call API (native Twilio) → callee is a persona agent's
Twilio number or a human cell. TODO(Hamza): real ElevenLabs wiring.
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class LaunchRequest(BaseModel):
    case_id: str
    entities: list[str] | None = None  # default: all detected entities


@router.post("/launch")
def launch_calls(req: LaunchRequest) -> dict:
    # TODO(Hamza):
    #  1. for each entity: build StrategyDossier (code: route + armed levers + anchor/target/floor)
    #  2. compile system prompt from prompts/negotiator_system.md + dossier + verbatim JobSpec
    #  3. POST to ElevenLabs outbound-call endpoint with agent_id + to_number
    #  4. insert calls rows; stream call_events via /tools logging
    return {
        "case_id": req.case_id,
        "launched": [
            {"call_id": "stub-call-1", "entity": "Mercy General Hospital", "status": "queued"},
            {"call_id": "stub-call-2", "entity": "Bay State Emergency Physicians", "status": "queued"},
            {"call_id": "stub-call-3", "entity": "Meridian Recovery Services", "status": "queued"},
        ],
    }


@router.get("/{call_id}")
def get_call(call_id: str) -> dict:
    # TODO(Hamza): read from Supabase
    return {"call_id": call_id, "status": "stub"}
