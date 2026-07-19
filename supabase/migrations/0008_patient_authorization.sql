-- The Negotiator — recorded patient authorization
-- Owner: Hamza. Apply via `supabase db push` (or run in the Supabase SQL editor).
--
-- Maya records herself, on the platform, authorizing the AI advocate to discuss,
-- negotiate, and adjust her account. The agent presents this the moment a rep
-- challenges authorization mid-call. There is NO native ElevenLabs mechanism to
-- play a stored clip into a live PSTN call (confirmed across the system-tools,
-- server-tools, client-tools, custom-LLM docs and the outbound-call API schema),
-- so the agent relays the recorded statement's exact words honestly and offers to
-- send the recording + a written release. See prompts/negotiator_system.md.
--
-- Three columns on the case:
--   authorization_path         — storage path in the authorizations bucket
--                                (authorizations/<case_id>.webm), signed at read time
--   authorization_recorded_at  — when the patient recorded it (the date the agent cites)
--   authorization_statement    — the exact words the patient read (verbatim relay source;
--                                it IS paper-trail evidence, shown on the case file)
--
-- Apply-safe / idempotent: `add column if not exists` is a no-op on re-run, and
-- until this migration lands the API's read/write of the columns simply skips
-- (best-effort db._run), so nothing breaks in the meantime.

alter table cases add column if not exists authorization_path text;
alter table cases add column if not exists authorization_recorded_at timestamptz;
alter table cases add column if not exists authorization_statement text;

-- Private bucket for the recorded authorization clips (separate from call
-- recordings so the paper trail keeps patient consent distinct from call audio).
insert into storage.buckets (id, name, public) values ('authorizations','authorizations', false)
  on conflict (id) do nothing;
