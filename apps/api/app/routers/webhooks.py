"""ElevenLabs post-call webhook → transcript + audio → outcome pipeline.

Post-call flow (PRD §6): store recording → OpenAI outcome extraction
(schema-validated CallOutcome) → honesty verifier (diff every stated figure
against dossier/benchmarks) → outcomes row → report builder.
"""
from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/elevenlabs")
async def elevenlabs_post_call(request: Request) -> dict:
    payload = await request.json()
    # TODO(Hamza):
    #  1. verify webhook signature
    #  2. download/store recording -> Supabase Storage recordings/
    #  3. OpenAI structured extraction -> CallOutcome (contracts/call_outcome.schema.json)
    #  4. honesty audit: every number in transcript ∈ {dossier, get_benchmark responses}
    #  5. insert outcomes row; mark call ended
    return {"received": True, "keys": list(payload.keys()) if isinstance(payload, dict) else []}
