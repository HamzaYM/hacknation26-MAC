# Workplan — Hamza (Engine, Orchestration, Scaffold) — critical path

**Mission:** scaffold by H2 so nobody blocks, then own everything between "spec confirmed" and "outcome logged". Read PRD §7–§9, §6, §12. Claude Code orchestrates the build with you.

## Deliverables
- [ ] **H0–H1: provision FIRST** — Twilio off-trial + buy all numbers (negotiator outbound + 4 persona inbound), create ElevenLabs agents (negotiator, intake, 4 personas), enter persona rows (agent IDs + numbers + human cells) in `personas` table
- [ ] H1–H2: scaffold lands (this repo) + Supabase project + run `supabase/migrations/0001_init.sql` + freeze H2 contracts (`contracts/`, yaml keys, levers.json shape) + README posted
- [ ] Red-flag engine in `apps/api` (deterministic, consumes J's config/tables): duplicate, upcode (dx rule), unbundle (NCCI), EOB mismatch, markup
- [ ] Dossier builder (code: route + armed levers + anchor/target/floor from config) + prompt compiler (`prompts/negotiator_system.md` + dossier + VERBATIM JobSpec)
- [ ] Server tools (`apps/api/app/routers/tools.py`): real state machine behind `report_lever_result` (ladder from yaml, stonewall triggers, floors enforced in code), `get_benchmark` from J's table, event logging → `call_events` (typed milestones — the War Room's primary feed)
- [ ] ElevenLabs wiring: outbound call trigger (native Twilio), post-call webhook → recording to Storage + OpenAI outcome extraction (CallOutcome schema) + honesty audit (figures vs. DB, case-facts vs. JobSpec)
- [ ] **First agent-vs-persona test call by H4** (turn-taking pathology check: persona greets first, negotiator wait-biased)
- [ ] Golden-recording replay endpoint (events on original timestamps + audio URL) for Susy
- [ ] Report builder: code ranking (rank key per §12) + OpenAI narrative (numbers interpolated by code)
- [ ] Demo-reset script (re-seed Maya's case, clear calls) + drive the UI on demo day

## Checkpoints you own (PRD §13)
H6 CP1: one full provider call with a lever-caused price move, twice in a row. H8 CP2: full E2E. H10 CP3: hard freeze. Descope order is pre-agreed — execute it without debate.

## Definition of done
One command boots web+api; provider call completes with a lever-caused price move twice in a row; 3 parallel calls reach structured outcomes (incl. the Stonewaller hang-up → documented decline); report generates with transcript citations + honesty-audit badge.
