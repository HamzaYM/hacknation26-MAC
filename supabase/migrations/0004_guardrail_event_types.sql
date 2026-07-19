-- The Negotiator — question-guardrail call_events types
-- Owner: Hamza. Apply via `supabase db push` (or run in the Supabase SQL editor).
--
-- The coverage gate logs a `coverage_gap` event when the agent walks off a
-- required-questions rung still missing tags, and the agent logs `read_back`
-- events when it reads a number/ref code back to the rep (A1/A6). Both need to
-- pass the call_events type CHECK, so widen it. db.CALL_EVENT_TYPES mirrors this.

alter table call_events drop constraint if exists call_events_type_check;
alter table call_events add constraint call_events_type_check
  check (type in ('transcript','tool_call','state_change','quote','escalation',
                  'coverage_gap','read_back'));
