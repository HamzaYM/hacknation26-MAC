# E2E audit — full-product drive, API probe, red team, observer critics

> 2026-07-18 late. Four independent passes over the live product: the orchestrator drove the
> full UI journey with Playwright (login → upload/parse → confirm → calls → War Room → case
> file), an API prober exercised every endpoint, a red team audited priorities, and two
> observer critics reviewed the captured screens for transparency and polish.

## What works (verified live)
Login for all three users · PDF upload → vision parse (23/23 line items verified, all 4 flags
with exact impacts) · confirm gate with voice card · simulated calls streaming to the War Room
· the case file with real-call audio · every tools endpoint honest to the answer key · zero
unhandled 500s across the error sweep except one (below) · question-coverage and end-call
gates behaving exactly per spec.

## Fixed during the audit
| Finding | Fix |
|---|---|
| Voice interview offline on the live site (missing env var), raw dev instructions shown to users | Env set + web restarted; graceful copy in flight (intake-capture PR) |
| /cases/{id}/action_plan 500 on every request (undefined names; frontend silently swallowed it) | PR #62, live |
| Report recommendation degraded into repeated sentences per demo re-run | PR #62 dedupe by entity, live |
| "Test Rep / TEST-REF-1" placeholder visible in the case file | Prober cleanup removed it |

## In flight (builders running)
| Finding | Branch |
|---|---|
| Confirm button dials nothing, dead-ends on /bills → will launch sims + route to War Room | feat/e2e-fixes |
| Case file missing from nav · War Room stale-LIVE clutter + raw-id card titles · favicon 404 | feat/e2e-fixes |
| .gitignore gaps (.claude 3.8GB, loose captures) · stale 3:30 video docs · scheduler misfire guard | feat/e2e-fixes |
| Voice interview answers never reach the case ($1,700 is a fixture) | feat/intake-capture |
| Simulated calls speak Maya's identity for ANY case; entities without persona mappings silently skipped | fix/simulator-identity-nsa |
| NSA flag never emitted by the real engine (Nina's story was fixture-only) | fix/simulator-identity-nsa |
| No simulated facility win reachable (achieved column always empty) | fix/simulator-identity-nsa (config-switchable) |
| 501(r) window + MA hardship path | feat/501r-hardship |

## Queued next (transparency round — from the observer critics)
1. **Fee disclosure in the product journey** (HIGH): the 25% / $2,000-cap model appears only on
   how-it-works. Add one line on the landing hero, the confirm screen, and the case file next
   to locked-in savings ("We keep 25% of what we save you. $0 if we save you nothing.").
2. **Regulatory clocks in plain English** (HIGH): FAP/GFE/FDCPA chips get expand-on-tap
   explanations plus a "handled by us" vs "needs you" marker.
3. **Provenance under every dollar figure** (HIGH): findings cite their evidence inline
   ("CPT 71046 billed twice on 06/02"); "people like you" names its benchmark.
4. Per-provider estimates on the confirm screen (the headline range covers only Mercy).
5. AI-self-identification + recording note at the consent moment.
6. Honesty tag repeated on each persona card in the War Room rail.
7. `calls.counterparty` dev-speak in the War Room footnote → plain language.
8. Privacy line on the upload screen (PHI moment), not only on login.
9. Bay State "Awaiting you" card gets a direct CTA; case-file header wording covers all parties.

## Data hygiene
- Duplicate sim outcomes accumulate on the demo case with every test launch (15 rows at audit
  time). Prune with `apps/api/.venv/bin/python scripts/prune_duplicate_outcomes.py --apply`
  (dry-run by default; never touches the archived real calls). Run before recording videos.
- One outcome carries "Bob" in the reference field (rep name leaked into ref); the case file's
  reference guard filters it client-side, engine-side validation queued with the transparency round.

## Red-team verdicts (decisions, standing)
- The 2x60s videos are the submission: production is owned (orchestrator generates footage from
  Kar Shin's scripts AFTER features land — Hamza's sequencing), assets checklist to follow.
- Record against a frozen main; merge-freeze during recording.
- Keep the outbound-dial flag off in .env; arm it only for deliberate call shots.
