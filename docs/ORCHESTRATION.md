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
5b. **Merges/conflict-resolution ONLY in worktrees** — never in the main checkout: it serves hagglfor.me live via next dev, and an in-progress merge broke the public site (07-18, transient).
5c. Negotiator brain LLM = **gpt-5.4** (Hamza, 07-18 evening: quality over latency — reps deserve a thinking counterpart; supersedes the earlier gemini-2.5-flash cost call). Pinned via `voice.negotiator_llm` in config; provisioning pushes it (and pacing) on every sync, voice still preserved unless pinned.
6. **Design source of truth = Susy.** She is producing the design + a design guide with Claude and will add both to the repo (needs a bit of time). Until then, `apps/web` styling is throwaway scaffold CSS — do NOT invest in visual design; when her guide lands, wire her designs and follow the guide exactly (Hamza, 2026-07-18).

## Demo production assets (pinned)
Live pitch deck: `apps/web/presentation/pitch.html` → route `/pitch-sf-2026` (`apps/web/app/pitch-sf-2026/route.ts`); 11 slides, self-contained, zero external requests.
- **Tech deck** (HTML, served): `apps/web/presentation/tech-video.html` → route `apps/web/app/tech-video/route.ts`. NOTE: route + script will need updating when demo production starts.
- **Tech script**: `docs/tech-video-script.md`
- **UI/UX video script**: `docs/video-a-uiux-script.md` · storyboard: `docs/video-a-storyboard.html` · assets: `docs/video-assets/`
- **Shot lists + judge Q&A**: `docs/demo-shot-lists.md` · findings/bug log: `docs/e2e-findings.md`
- **Sequencing (Hamza)**: all features land first, then video production; scripts may change, re-read before shooting.

## Current state (update me!)
- ✅ PRD.md (adversarially + web-verified) · scaffold on main (`689e858`) · README (`998c2bd`) · large-file policy (`b426539`)
- ✅ PR #1 ORCHESTRATION.md · PR #2 `docs/setup-checklist.html` · **PR #3 engine core** · **PR #11 MGH retune** · **PR #12 fixture-derived PDFs** · **PR #13 product UI** · **PR #14 Supabase provisioning**
- ✅ **MGH real-data adoption** — benchmarks reconciled to real MGH: cash $2,633.25 / neg-median $999.30 / upcode $2,011.21; arc endpoints unchanged. Boston MA location, BCBS-MA, Bay State ER.
- ✅ Engine facts: demo case → exactly 4 flags (412/2011.21/642/412); dossier anchor $657 / target $876 / floor $1,700; $1,650 settle ⇒ `escalation_required`; hangup ⇒ terminal documented_decline
- ✅ **Backend wiring (PR #18/#19):** Supabase persistence + simulated call driver + report endpoint. Frontend launch/confirm/report wired. 58/58 tests green.
- ✅ **Document parsing (PR #24):** POST /documents/parse with OpenAI vision (gpt-5.6-terra), structured outputs, reconciliation. Both demo PDFs parse to exact match, all 4 flags fire on parsed data.
- ✅ **Data hardening (PR #27):** NCCI table extended with production bundles + subsumption logic, extraction prompt doc, unicode apostrophe fix, TODO markers cleared.
- ✅ **Test use-cases + voice tuning (PR #20):** Persona probes (L1), negotiator conduct rules, only-if-asked disclosure mode, eval harness with call-efficiency soft check.
- ✅ **Intake + login (PR #25):** Supabase password auth, document parse flow, voice interview widget.
- ✅ Provisioning: ElevenLabs 6 agents live · Supabase live (migration 15/15, buckets, realtime, benchmarks+personas seeded w/ agent IDs) · Demo auth user (maya@hagglfor.me)
- ⏳ Twilio: paid account + $20 balance ✅; number purchase blocked on Jay's Trust Hub KYC (must reach "Twilio Approved"); then scripts/provision_twilio.py buys 2 MA numbers + imports/assigns in ElevenLabs
- ⏳ Remaining: ElevenLabs webhook-tool registration + cloudflared tunnel + first PSTN call (post-KYC). Browser-session calls work now.
- ✅ Product name: **Haggl** (design-system.md is styling law)
- ⏳ hagglfor.me (Cloudflare, Hamza's account) — after deployment; never critical path
- Known nit parked: duplicate-detection modifier exemption (real bills only, not demo-blocking).

## Endgame state (07-19, ~2h to submission deadline 9:00 AM ET)
- ~45 PRs merged; suite **351 green**; live site clean post web-cleanup (#91): no Voice tab, War Room last in nav, no dev copy.
- **The hero call is real**: conv_8701kxwv (212s, PSTN a2a, Jason negotiator vs Morgan persona-supervisor) ran the full arc $4,287 → $3,875 → $2,400 → $1,650, ref MG-ADJ-2247, archived into Maya's case file with audio. Ticker fix (#95) makes real calls emit quote events.
- Case file /report: hero settlement leads Resolved; 5 real-call audio players + authorization clip. Demo DB reset applied (scripts/demo_reset.py).
- Submission kit: docs/submission/ (form copy, checklist, gallery). Judge assets: deck/judge-guide.pdf (screenshot user guide), /technical-architecture live route, deck/haggl-pitch.pptx + .pdf.
- In flight: feat/videos-v2 builder (tech + demo v2 with v3 multi-voice guide VO — Brian/Sarah/Bella/Jason — real hero-call audio block, Jay VO cadence docs, refreshed judge PDF).
- Hamza uploads: team picture, team video (filmed), Account IDs, form copy paste, videos when v2 lands. Jay records VO from docs/vo/ cadence scripts; mux + finalize after.

## In-flight (pinned 07-18 ~17:45 for compaction recovery — historical)
- **Deck (PRIORITY)**: Opus agent building deck/haggl-pitch.pptx on branch feat/pitch-deck — 8-slide/4:45 plan from the research brief; captures own site screenshots; voice-guide enforced; PRs when done.
- **Multi-user + real-call plumbing**: agent on feat/multi-user-and-realcall — Dan/Nina users+cases, /calls/place-real + conversation_id persistence (A1), UUID default call_id fix (A2), archive_call.py run on both real conversations (Jay-call conv_9301kxvs…, a2a conv_8001kxvt…), shot-list C3 wording fix.
- **Visuals**: agent on feat/dashboard-warroom-visuals — /bills deadlines strip, multi-call War Room overview, price-flash, milestone icons. For Susy's review.
- Orchestrator merges each PR on landing, then Playwright-verifies. Judge scorecard v2 (arch 7.5 / creativity 8 / workflow 6) + fix ranking: in the workflow journal wf_5189005d.
- Susy's voice IDs (Alex PK6t0r2iXSJEz1l0Gy4k · Morgan IUr28Q1jJWtnKBQJWsGP · Riley urYrjlrwA2jxqHzz2wHT) 400 on assign — likely must be added to the workspace voice library first (dashboard), then assign Alex→negotiator, ask Hamza for Morgan/Riley mapping.
- Servers on Hamza's machine serve hagglfor.me via cloudflared tunnel "haggl": next dev :3000, uvicorn :8000 — keep alive; use 127.0.0.1 not localhost.

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
| 07-18 | **Submission format: 60-second UI/UX demo video + 60-second tech demo video** (replaces the 3:30 single video — Kar Shin's script + deck need restructuring; compliance auditor producing both shot lists) | Hamza |
| 07-18 | Page copy must pass Hamza's voice guide (docs/voice/ — "Page copy" register in voice-profile-addendum.md; standing rules: no em-dashes, no "not just X, it's Y" framing). Copy pass runs after the current build round merges | Hamza |
| 07-18 | Susy keeps pushing UI work — orchestrator consolidates (watch origin/susy + PRs, merge + reconcile) | Hamza |
| 07-18 | Telephony: Jay's Twilio account is the path (Hamza's KYC unfixable); Jay's Trust Hub profile must reach "Twilio Approved" before scripts/provision_twilio.py can buy numbers. Browser-session calls are the working baseline meanwhile | Hamza |

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
`PRD.md` (the plan) · `docs/workplans/*` (per person) · `data/pipeline/README.md` (Jay's data spec) · `docs/claude-headless-notes.md` (subscription cost routing) · `contracts/` (frozen schemas) · `config/verticals/medical_bills.yaml` (config-not-code) · memory dir (Claude-private prefs)
