"""Caller endpoints — launch and inspect calls.

POST /launch creates REAL `calls` rows (one per entity, real UUIDs) plus a
persisted StrategyDossier per entity, for any fixture case (Maya/Dan/Nina —
app/fixtures_users.py). With simulate=true each call is replayed through the
simulated driver (app/simulator.py) as a background task, so the War Room
renders a live negotiation without ElevenLabs/Twilio.

POST /place-real dials the negotiator agent over PSTN (app/elevenlabs_calls.py)
with the calls row created BEFORE dialing and the returned conversation_id
persisted on it — so mid-call tools and the post-call webhook (transcript +
audio) land in-product instead of only in the ElevenLabs dashboard.
"""
import os
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from .. import db, elevenlabs_calls
from ..config import load_vertical
from ..engine.dossier import build_dossier
from ..fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC, demo_benchmarks, demo_flags
from ..fixtures_users import OWNER_EMAIL_BY_CASE_ID, flags_for_spec, spec_for_case
from ..models import JobSpec
from ..simulator import ENTITY_PERSONAS, play_calls

router = APIRouter()

# scripts/place_test_call.py constants — the provisioned negotiator line.
STONEWALLER_NUMBER = "+18576757033"
NEGOTIATOR_PHONE_ID = "phnum_4701kxvqv879f7d9sm8nvsg2akce"


class LaunchRequest(BaseModel):
    case_id: str
    entities: list[str] | None = None  # default: all detected entities
    simulate: bool = False             # replay through the simulated driver


@router.post("/launch")
def launch_calls(req: LaunchRequest, background_tasks: BackgroundTasks) -> dict:
    spec_dict = spec_for_case(req.case_id)
    if spec_dict is None:
        raise HTTPException(404, "case not found (only the fixture cases exist so far)")
    spec = JobSpec.model_validate(spec_dict)
    case_id = spec_dict["case_id"]
    flags = flags_for_spec(spec_dict)
    # no-op without a DB; makes calls.case_id FK resolve
    db.ensure_case(case_id, spec_dict, OWNER_EMAIL_BY_CASE_ID.get(case_id))

    launched: list[dict] = []
    sim_specs: list[tuple[str, str, str, str]] = []
    for entity in spec.entities:
        if req.entities and entity.name not in req.entities:
            continue
        # ENTITY_PERSONAS only covers the hand-authored Maya scripts; any other
        # case (including entity kinds Maya doesn't have) still gets a
        # simulated call — simulator.build_sequence dispatches to the
        # case-generic driver for any case_id != DEMO_CASE_ID regardless of
        # which persona name is threaded through here.
        persona = ENTITY_PERSONAS.get(entity.kind, "generic")
        call_id = str(uuid.uuid4())
        dossier = build_dossier(spec, flags, demo_benchmarks(), load_vertical(), entity=entity)
        dossier_id = db.insert_dossier(case_id, dossier)
        db.insert_call(call_id, case_id, counterparty="agent", dossier_id=dossier_id)
        launched.append({"call_id": call_id, "entity": entity.name, "status": "queued"})
        sim_specs.append((call_id, persona, case_id, entity.name))

    if req.simulate and sim_specs:
        background_tasks.add_task(play_calls, sim_specs)
    return {"case_id": req.case_id, "launched": launched}


class PlaceRealRequest(BaseModel):
    to_number: str | None = None  # default: the Stonewaller's provisioned line


@router.post("/place-real")
def place_real_call(req: PlaceRealRequest) -> dict:
    """Real PSTN dial with the calls row created BEFORE the call connects."""
    to_number = req.to_number or STONEWALLER_NUMBER
    spec = JobSpec.model_validate(DEMO_JOB_SPEC)
    entity = spec.entities[0]

    call_id = str(uuid.uuid4())
    db.ensure_demo_case()
    dossier = build_dossier(spec, demo_flags(), demo_benchmarks(), load_vertical(), entity=entity)
    dossier_id = db.insert_dossier(DEMO_CASE_ID, dossier)
    counterparty = "agent" if to_number == STONEWALLER_NUMBER else "human"
    db.insert_call(call_id, DEMO_CASE_ID, counterparty=counterparty, dossier_id=dossier_id)

    try:
        resp = elevenlabs_calls.outbound_call(
            os.environ.get("ELEVENLABS_AGENT_ID_NEGOTIATOR", ""),
            os.environ.get("ELEVENLABS_PHONE_NUMBER_ID", NEGOTIATOR_PHONE_ID),
            to_number,
            conversation_initiation_client_data={
                "dynamic_variables": {
                    "patient_name": spec.patient.get("legal_name", ""),
                    "account_number": spec.bill.account_number,
                    "target_entity": f"{entity.name} patient financial services",
                    "route": dossier.route,
                    "anchor": f"{dossier.anchor:.0f}",
                    "target": f"{dossier.target:.0f}",
                }
            },
        )
    except httpx.HTTPError as err:
        db.update_call_status(call_id, "failed")
        raise HTTPException(502, f"outbound dial failed: {err}") from err

    conversation_id = resp.get("conversation_id")
    if conversation_id:
        db.set_call_conversation(call_id, conversation_id)
        db.update_call_status(call_id, "ringing")
    elif not resp.get("enabled"):
        db.update_call_status(call_id, "failed")

    out = {
        "call_id": call_id,
        "case_id": DEMO_CASE_ID,
        "to_number": to_number,
        "enabled": resp.get("enabled", False),
        "conversation_id": conversation_id,
        "war_room_url": f"https://hagglfor.me/warroom?call_id={call_id}",
    }
    if resp.get("note"):
        out["note"] = resp["note"]
    return out


@router.get("/{call_id}")
def get_call(call_id: str) -> dict:
    row = db.get_call(call_id)
    if row is None:
        raise HTTPException(404, "call not found")
    return row
