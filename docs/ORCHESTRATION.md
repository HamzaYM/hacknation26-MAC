# ORCHESTRATION — living hub (Claude = orchestrating agent)

> **Purpose:** the single doc Claude re-reads to re-anchor after context compaction, and the team
> reads for current truth. Update whenever a decision lands, a PR merges, or provisioning changes.
> Last update: **2026-07-18** (post-scaffold, PR workflow begins).

## Operating rules
1. **PRs only** — branch → push → `gh pr create` → squash-merge. Never straight to main (Hamza, 2026-07-18).
2. **All product decisions go to Hamza** — ask with a recommendation; never decide silently.
3. Claude orchestrates: dispatches agents/workflows (any model/effort), integrates, verifies. Hamza executes vendor-site provisioning from Claude's checklists.
4. Teammates may push PRD updates as versions (via PRs).
5. Demo-optimized: when a choice trades robustness vs. demo reliability, demo wins (Hamza, 2026-07-18).
6. **Design source of truth = Suzy.** She is producing the design + a design guide with Claude and will add both to the repo (needs a bit of time). Until then, `apps/web` styling is throwaway scaffold CSS — do NOT invest in visual design; when her guide lands, wire her designs and follow the guide exactly (Hamza, 2026-07-18).

## Current state (update me!)
- ✅ PRD.md (adversarially + web-verified) · scaffold on main (`689e858`) · README (`998c2bd`) · large-file policy (`b426539`)
- ✅ PR #1 ORCHESTRATION.md · PR #2 `docs/setup-checklist.html` (Hamza's provisioning checklist — LOCAL html, per preference: no artifacts) · **PR #3 engine core merged (`84af5b7`): flags + dossier + ladder state machine, 27/27 tests green on main**
- ✅ **MGH real-data re-tune + Boston MA relocation landed** (one commit, per the locked-numbers rule): seeds/answer key/fixtures/tests/PDFs/PRD all reconciled to real MGH cash $2,633.25 / negotiated median $999.30 / upcode $2,011.21; arc endpoints unchanged
- ✅ Engine facts: demo case → exactly 4 flags (412/2011.21/642/412); dossier anchor $657 / target $876 / floor $1,700; $1,650 settle ⇒ `escalation_required` (supervisor beat); hangup ⇒ terminal documented_decline
- ⏳ **Provisioning (Hamza, via docs/setup-checklist.html):** Twilio paid ($20 total, prices confirmed) + numbers + verified caller ID · ElevenLabs agents ×6 + number import · Supabase project + migration + keys → `.env` · OpenAI key · consents · collaborators. **Blocked on Hamza reporting "env filled" + persona numbers/IDs.**
- ⏳ Next build steps once env lands: ElevenLabs wiring (outbound call trigger, webhook tools registration, post-call webhook + tunnel), Supabase persistence (state machine + call_events), prompt compiler. Waiting on Suzy's design guide before any real frontend styling.
- ⏳ hagglfor.me (Cloudflare, Hamza's account) — after something is deployed; never critical path
- Known nits parked: unicode-apostrophe normalization in stonewall matching; duplicate-detection modifier exemption (real bills).

## Decision log
| Date | Decision | By |
|---|---|---|
| 07-18 | Vertical: medical bills; no real hospital calls; counter-agents + 1 human role-play | Hamza |
| 07-18 | ElevenLabs = voice loop/voices; OpenAI = offline text+vision; headless Claude for prose (see docs/claude-headless-notes.md) | Hamza |
| 07-18 | Stack: Next.js + FastAPI + Supabase; all calls over Twilio PSTN | Hamza |
| 07-18 | Scope: provider ladder + collections + charity + 3 levers; insurer call cut | Hamza |
| 07-18 | Raw MRFs (450MB+) never hosted: filter locally, commit slim extract; R2 only if sharing needed | Hamza |
| 07-18 | Demo numbers locked: $8,432 billed / $4,287 balance / EOB $3,875 / Medicare $438 / settle $1,650 (−62%) — change ONLY together with `data/seed/demo_answer_key.json` + PRD §10.3 + §14. **Adopted 07-18: real MGH MRF cash $2,633.25 / negotiated median $999.30 / upcode $2,011.21** (arc endpoints unchanged) | Hamza |
| 07-18 | Demo relocated to Boston MA (Maya, facility, insurer BCBSMA, ER group "Bay State Emergency Physicians") | Hamza |
| 07-18 | Facility name stays fictional ("Mercy General Hospital", Boston); MGH named only as the data source — benchmarks labeled "derived from a real Boston hospital's published price file", never the negotiation counterparty | Hamza |

## Key facts Claude must not re-derive
- Contracts frozen per PRD §12 (H2/H3/H8 schedule); `data/seed/demo_answer_key.json` is the single source of demo truth (`transform.py --check` gates it).
- Twilio trial can't call unverified numbers (21608) — paid account is H0-blocking.
- Agent-vs-agent over PSTN undocumented → H4 test is go/no-go; fallback = persona calls as recorded browser sessions.
- Port 8000 on Hamza's machine has a stray IPv6 listener → always use `127.0.0.1`.
- ElevenLabs: "webhook tools" (mid-call), 3 post-call webhook types (transcription / audio-base64 / initiation-failure), audio also via `GET /v1/convai/conversations/{id}/audio`.

## Board
- Active PRs: (update as opened/merged)
- Agents/workflows in flight: engine-core builder; Twilio cost research (Sonnet)
- Harness task list mirrors this — keep both current.

## Doc index
`PRD.md` (the plan) · `docs/workplans/*` (per person) · `data/pipeline/README.md` (J's data spec) · `docs/claude-headless-notes.md` (subscription cost routing) · `contracts/` (frozen schemas) · `config/verticals/medical_bills.yaml` (config-not-code) · memory dir (Claude-private prefs)
