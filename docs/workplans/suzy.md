# Workplan — Suzy (UX & Frontend)

**Mission:** the six-screen user journey in `apps/web/`, with the live-call **War Room** as the demo's money shot. Read PRD §11 first, then §12 and §8.2 (the ladder rungs your progress indicator renders).

## Deliverables
- [ ] H0–H2 (no dependencies): flow map + wireframes for all six screens (PRD §11)
- [ ] Screens: `/onboard` → `/intake` (upload + ElevenLabs widget card) → `/confirm` (red-flag chips, savings ranges, **boost panel**, the one Confirm button) → `/warroom` → `/report` (+ Case Timeline tab)
- [ ] War Room: parallel call cards · dossier panel (armed levers + citations) · lever-ladder indicator (`rung_advanced` events) · **price ticker with delta badge readable from the back of the room** · AI-disclosure indicator · outcome badges
- [ ] Supabase Realtime wiring on `call_events` (see `lib/realtime.ts` stub; primary feed = typed milestone events, transcript text is garnish)
- [ ] Golden-recording playback mode: replay stored `call_events` on original timestamps + recording audio, through the IDENTICAL live-card code path (Hamza provides the replay endpoint). This is the demo fallback AND the video rig.
- [ ] States: in-progress, escalation, decline (incl. hang-up), settlement-confirmed

## You consume / you produce
- Consume: scaffold + contracts (H2), `call_events` stream (H5), `report` data (H8). Fixture case: `GET localhost:8000/cases/demo` works from H2 — build against it.
- Produce: integration-ready UI by **H8**, polish by H12. You also operate the fallback switcher on demo day (and are backup phone rep — see `prompts/personas/human_role_play_guide.md`).

## Definition of done
Full click-through of all six screens against live data during a real call; the $4,287 → $1,650 price move is visible at a glance; playback mode indistinguishable from live.
