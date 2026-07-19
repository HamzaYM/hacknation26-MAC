-- The Negotiator — per-case voice preference (Voice Picker feature)
-- Owner: Hamza. Apply via `supabase db push` (or run in the Supabase SQL editor).
--
-- Standalone table (no ALTER on cases) so it rebases cleanly against the
-- multi-user branch. One chosen voice per case; the web UI mirrors the same
-- value to localStorage so the picker works even before this migration lands.

create table if not exists case_voice_prefs (
  case_id uuid primary key references cases(id) on delete cascade,
  voice_id text not null,                 -- ElevenLabs voice_id of the cloned voice
  voice_label text,                       -- human label at time of choice (e.g. "Alex")
  updated_at timestamptz not null default now()
);
