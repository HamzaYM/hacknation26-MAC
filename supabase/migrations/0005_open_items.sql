-- The Negotiator — open items (parked topics that persist across calls)
-- Owner: Hamza. Apply via `supabase db push` (or run in the Supabase SQL editor).
--
-- Live-call feedback (Hamza, 07-18): when a lever hits an impasse the agent PARKS
-- it as an open item and moves on, instead of forcing a supervisor. Parked items
-- become scheduled callbacks (next_attempt_at); resolved ones carry a resolution_date.
-- The case-file UI reads these back from /cases/{id}/report.

create table if not exists open_items (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  lever text,                                            -- the ladder topic that stalled
  detail text,                                           -- why it parked / what was agreed
  amount_at_stake numeric(10,2),
  status text not null default 'open'
    check (status in ('open','scheduled','resolved')),
  created_call_id uuid references calls(id) on delete set null,
  resolved_call_id uuid references calls(id) on delete set null,
  resolution_date date,                                  -- set when status='resolved'
  next_attempt_at timestamptz,                           -- set when status='scheduled'
  reference_number text,
  created_at timestamptz not null default now()
);

create index if not exists open_items_case_idx on open_items (case_id);
create index if not exists open_items_scheduled_idx on open_items (status, next_attempt_at);

-- Widen the call_events type CHECK for the two new event types: `topic_parked`
-- (the agent set a lever aside) and `callback_due` (a scheduled callback fired while
-- outbound dialing is flag-off — logged, not dialed). db.CALL_EVENT_TYPES mirrors this.
alter table call_events drop constraint if exists call_events_type_check;
alter table call_events add constraint call_events_type_check
  check (type in ('transcript','tool_call','state_change','quote','escalation',
                  'coverage_gap','read_back','topic_parked','callback_due'));
