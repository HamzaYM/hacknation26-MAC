-- The Negotiator — per-question coverage call_events type
-- Owner: Hamza. Apply via `supabase db push` (or run in the Supabase SQL editor).
--
-- The War Room coverage panel watches required questions flip red→green live. The
-- state machine already tracks questions_covered per call and logs `coverage_gap`
-- on the one-time block; this adds a `question_covered` event (payload {tag, rung})
-- emitted by report_lever_result the moment a new required tag is covered, so the
-- panel can flip each row without polling. Widen the call_events type CHECK for it.
-- db.CALL_EVENT_TYPES mirrors this.

alter table call_events drop constraint if exists call_events_type_check;
alter table call_events add constraint call_events_type_check
  check (type in ('transcript','tool_call','state_change','quote','escalation',
                  'coverage_gap','read_back','topic_parked','callback_due',
                  'question_covered'));
