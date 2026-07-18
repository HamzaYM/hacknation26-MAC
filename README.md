# The Negotiator — Medical Bills

Hack-Nation 6th Global AI Hackathon · Challenge 01 (ElevenLabs) · Team: Suzy · J · Hamza · Kar Shin

*An AI advocate that reads your hospital bill, finds the errors and the law on your side, calls the billing office, and talks the price down on a live call.*

**Start here → [`PRD.md`](PRD.md), then your own file in [`docs/workplans/`](docs/workplans/).**

## Architecture (PRD §6)

Next.js (UI) ↔ FastAPI (state machine · webhook tools · post-call webhooks) ↔ Supabase (Postgres · Storage · **Realtime → live War Room**) ↔ **ElevenLabs Agents** (voice loop, brain LLM billed in-platform) ↔ **Twilio** (every call is a real PSTN call) — plus OpenAI for offline text/vision. Negotiation *policy* is deterministic server-side code; the LLM is the mouth, not the brain-stem (PRD §7).

## Repo map & ownership

| Path | What | Owner |
|---|---|---|
| `PRD.md` | The plan. Read it first. | everyone |
| `apps/web/` | Next.js frontend — six screens (PRD §11) | **Suzy** |
| `apps/api/` | FastAPI — engine, tools, webhooks, state machine | **Hamza** |
| `contracts/` | Frozen JSON Schemas (job_spec, benchmark_row, dossier, call_outcome) | Hamza |
| `config/verticals/` | The config-not-code boundary (levers, flags, thresholds, voice) | Hamza keys / **J** values |
| `data/pipeline/` + `data/seed/` | CMS/MRF pipeline → benchmarks; demo answer key | **J** |
| `prompts/` | Negotiator/intake prompts, personas, imperfection + verbalization guides | **Kar Shin** (+ Hamza) |
| `supabase/migrations/` | DB schema | Hamza |
| `docs/workplans/` | Per-person marching orders | everyone (theirs) |

## Quickstart (each teammate)

```bash
cp .env.example .env    # fill in — see comments; Supabase keys from the project dashboard

# Frontend (Suzy)
cd apps/web && npm install && npm run dev          # → http://localhost:3000

# Backend (Hamza; works with zero external services — fixture data built in)
cd apps/api && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000          # → http://localhost:8000/health
curl localhost:8000/cases/demo                     # Maya's fixture JobSpec

# Data (J)
cd data/pipeline && python3 transform.py --check   # validates seed vs demo answer key

# DB (once): run supabase/migrations/0001_init.sql in the Supabase SQL editor
```

## Demo-critical gotchas (web-verified 2026-07)
- **Twilio trial can't call unverified numbers** (error 21608, ≤5 verified) — upgrade to paid at H0.
- **Agent-vs-agent over PSTN is undocumented** — H4 test is the go/no-go; fallback = persona calls as recorded browser/widget sessions, PSTN for the live human call.
- **Supabase free tier**: 1GB storage / 7-day auto-pause — provision at H0, ping it demo-day morning.
- **Cost saver**: offline prose can run on Claude Max subscriptions via headless `claude -p` — see `docs/claude-headless-notes.md`. Vision parsing stays on OpenAI.

## Source research (repo root)
`Challenge.pdf` · `Research.md` · `conversational-tactics-and-psychology.md` · `operational-call-flow-spec.md` · `negotiator-intake-data-schema.md` · `The Negotiator - Visual Brief.dc.html`
