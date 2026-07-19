# The Negotiator — Medical Bills 🩺📞

Hack-Nation 6th Global AI Hackathon · Challenge 01 (powered by ElevenLabs) · future home: **hagglfor.me**

*An AI advocate that reads your hospital bill, finds the errors and the law on your side, calls the billing office, and talks the price down on a live call.*

The demo in one line: Maya's $4,287 ER balance → agent finds 4 seeded billing errors → cites Medicare ($438) and the hospital's **own posted cash price** ($2,633.25) → live settlement at **$1,650, −62%** — every step caused by data and tools, not script.

## Status

✅ PRD complete (adversarially + web-verified) · ✅ scaffold boots (web, api, data checks green) · ⏳ next: **H0 provisioning** — Twilio **paid** account + all numbers (trial can't call unverified numbers — error 21608), ElevenLabs agents created, Supabase project up + `supabase/migrations/0001_init.sql` run.

## Start here (first hour, per person)

| Person | Read | Then |
|---|---|---|
| **Susy** — UX/frontend | [PRD §11](PRD.md) + [your workplan](docs/workplans/susy.md) | Wireframe the six screens; `apps/web` runs now (see Quickstart) |
| **J** — data/benchmarks | [PRD §10](PRD.md) + [your workplan](docs/workplans/j.md) | **Start the CMS download immediately** (longest lead); `data/pipeline/README.md` is your spec |
| **Hamza** — engine/orchestration | [PRD §7–9](PRD.md) + [your workplan](docs/workplans/hamza.md) | Provision Twilio/ElevenLabs/Supabase FIRST, then tool endpoints |
| **Kar Shin** — personas/voice/video | [PRD §14+§9](PRD.md) + [your workplan](docs/workplans/kar-shin.md) | Persona prompts v0 (`prompts/personas/`) + the voice-style layer |

Claude Code orchestrates the build (integration, wiring, unblocking) with Hamza.

## Architecture (PRD §6)

Next.js (UI) ↔ FastAPI (state machine · webhook tools · post-call webhooks) ↔ Supabase (Postgres · Storage · **Realtime → live War Room**) ↔ **ElevenLabs Agents** (voice loop, brain LLM billed in-platform) ↔ **Twilio** (every call is a real PSTN call) — plus OpenAI for offline text/vision. Negotiation *policy* is deterministic server-side code; the LLM is the mouth, not the brain-stem (PRD §7).

The full walkthrough lives in **[docs/architecture.md](docs/architecture.md)**: two diagrams plus five design theses (LLM as mouth · structural honesty · verticals as config · reconciliation-gated real data · one transport), each tied to a file you can open.

## Repo map & ownership

| Path | What | Owner |
|---|---|---|
| `PRD.md` | The plan. Read it first. | everyone |
| `apps/web/` | Next.js frontend — six screens (PRD §11) | **Susy** |
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
cp .env apps/web/.env.local    # required — the browser needs the NEXT_PUBLIC_* vars

# Frontend (Susy)
cd apps/web && npm install && npm run dev          # → http://localhost:3000
# demo logins: see the demo-accounts table below

# Backend (Hamza; works with zero external services — fixture data built in)
cd apps/api && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000          # → http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/cases/demo              # Maya's fixture JobSpec

# Data (J)
cd data/pipeline && python3 transform.py --check   # validates seed vs demo answer key

# DB (once): run supabase/migrations/0001_init.sql in the Supabase SQL editor
```

(Use `127.0.0.1`, not `localhost` — stray IPv6 listeners on port 8000 will confuse curl.)

## Demo accounts

All passwords: `HagglDemo2026!` (seed/repair with `python scripts/seed_demo_users.py`).
Logging in on hagglfor.me routes `/bills` to that user's case; logged out you get Maya's.

| Login | Case | The story |
|---|---|---|
| `maya@hagglfor.me` | Mercy General ER, $4,287 balance | The flagship: 4 seeded flags (duplicate/upcode/unbundle/EOB), 3 entities, −62% settlement arc |
| `dan@hagglfor.me` | $2,140 sold to Meridian Recovery Services | Collections route: duplicate + markup flags, $900 floor, lump-sum-anchor ladder |
| `nina@hagglfor.me` | $3,120 out-of-network anesthesia balance bill | No Surprises Act: `nsa` + EOB-mismatch flags — cite the statute and file a complaint, don't negotiate |

## Demo-critical gotchas (web-verified 2026-07)
- **Twilio trial can't call unverified numbers** (error 21608, ≤5 verified) — upgrade to paid at H0.
- **Agent-vs-agent over PSTN is undocumented** — the H4 loop test is the go/no-go; fallback = persona calls as recorded browser/widget sessions, PSTN reserved for the live human call.
- **Supabase free tier**: 1GB storage / 500MB DB / 7-day auto-pause — provision at H0, ping it demo-day morning. **Raw MRFs (450MB+) never go there**: stream-filter locally, commit only the slim extract; share raw files via Cloudflare R2 if ever needed (`data/pipeline/README.md`).
- **Consent paper trail**: text/Slack consent from every teammate whose phone gets dialed (FCC treats AI voice as TCPA-covered regardless of who's called).
- **Cost saver**: offline prose runs free on Claude Max subscriptions via headless `claude -p` — see `docs/claude-headless-notes.md`. Vision parsing stays on OpenAI.

## Source research (repo root)
`Challenge.pdf` · `Research.md` · `conversational-tactics-and-psychology.md` · `operational-call-flow-spec.md` · `negotiator-intake-data-schema.md` · `The Negotiator - Visual Brief.dc.html`
