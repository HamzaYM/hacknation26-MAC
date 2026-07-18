"""The Negotiator — FastAPI backend.

Owner: Hamza (+ Claude Code as orchestrator).
Boots with fixture data and no external services: `uvicorn app.main:app --reload --port 8000`.
Routers:
  /cases     — case CRUD + JobSpec (Estimator)
  /documents — bill/EOB PDF upload → vision parse + reconciliation (Estimator)
  /calls     — launch/inspect calls (Caller)
  /tools     — ElevenLabs server-tool endpoints, hit MID-CALL by the voice agent
  /webhooks  — ElevenLabs post-call webhook (transcript + audio)
"""
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import cases, calls, documents, tools, webhooks

app = FastAPI(title="The Negotiator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router, prefix="/cases", tags=["cases"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(calls.router, prefix="/calls", tags=["calls"])
app.include_router(tools.router, prefix="/tools", tags=["tools"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])


@app.get("/health")
def health() -> dict:
    return {"ok": True}
