"""Caller endpoints — launch and inspect calls.

POST /launch creates REAL `calls` rows (one per entity, real UUIDs) plus a
persisted StrategyDossier per entity. With simulate=true each call is replayed
through the simulated driver (app/simulator.py) as a background task, so the
War Room renders a live negotiation without ElevenLabs/Twilio. Real outbound
dialing lives in app/elevenlabs_calls.py (feature-flagged until numbers exist).
"""
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from .. import db
from ..config import load_vertical
from ..engine.dossier import build_dossier
from ..fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC, demo_benchmarks, demo_flags
from ..models import JobSpec
from ..simulator import ENTITY_PERSONAS, play_calls

router = APIRouter()


class LaunchRequest(BaseModel):
    case_id: str
    entities: list[str] | None = None  # default: all detected entities
    simulate: bool = False             # replay through the simulated driver


@router.post("/launch")
def launch_calls(req: LaunchRequest, background_tasks: BackgroundTasks) -> dict:
    if req.case_id not in (DEMO_CASE_ID, "demo"):
        raise HTTPException(404, "case not found (only the demo fixture exists so far)")
    spec = JobSpec.model_validate(DEMO_JOB_SPEC)
    db.ensure_demo_case()  # no-op without a DB; makes calls.case_id FK resolve

    launched: list[dict] = []
    sim_specs: list[tuple[str, str]] = []
    for entity in spec.entities:
        if req.entities and entity.name not in req.entities:
            continue
        persona = ENTITY_PERSONAS.get(entity.kind)
        if persona is None:
            continue
        call_id = str(uuid.uuid4())
        dossier = build_dossier(spec, demo_flags(), demo_benchmarks(), load_vertical(), entity=entity)
        dossier_id = db.insert_dossier(DEMO_CASE_ID, dossier)
        db.insert_call(call_id, DEMO_CASE_ID, counterparty="agent", dossier_id=dossier_id)
        launched.append({"call_id": call_id, "entity": entity.name, "status": "queued"})
        sim_specs.append((call_id, persona))

    if req.simulate and sim_specs:
        background_tasks.add_task(play_calls, sim_specs)
    return {"case_id": req.case_id, "launched": launched}


@router.get("/{call_id}")
def get_call(call_id: str) -> dict:
    row = db.get_call(call_id)
    if row is None:
        raise HTTPException(404, "call not found")
    return row
