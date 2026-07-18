-- The Negotiator — initial schema
-- Owner: Hamza. Apply via `supabase db push` (or run in the Supabase SQL editor).

create extension if not exists "pgcrypto";

-- ── Cases ────────────────────────────────────────────────────────────────
create table if not exists cases (
  id uuid primary key default gen_random_uuid(),
  patient jsonb not null default '{}'::jsonb,           -- legal_name, dob, address, relationship, ssn_last4
  insurance jsonb not null default '{}'::jsonb,         -- payer_name, member_id, group_number, phones, plan_type
  financial_profile jsonb not null default '{}'::jsonb, -- household_income, household_size, employment, lump_sum_available, max_monthly
  authorizations jsonb not null default '{}'::jsonb,    -- hipaa_roi/insurer_rep/aor/recording: not_started|submitted|confirmed (mocked)
  status text not null default 'intake',                -- intake|confirmed|calling|resolved
  created_at timestamptz not null default now()
);

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  kind text not null check (kind in ('bill','eob')),
  storage_path text not null,
  parsed jsonb,
  parse_status text not null default 'pending',         -- pending|parsed|failed
  created_at timestamptz not null default now()
);

create table if not exists line_items (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  source text not null check (source in ('bill','eob')),
  cpt text not null,
  description text,
  date_of_service date,
  units int not null default 1,
  billed_amount numeric(10,2),
  allowed_amount numeric(10,2),
  plan_paid numeric(10,2),
  patient_responsibility numeric(10,2),
  billing_entity text                                    -- facility | er_physician_group | radiology | collections …
);

create table if not exists flags (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  line_item_id uuid references line_items(id) on delete set null,
  type text not null check (type in ('duplicate','upcode','unbundle','phantom','eob_mismatch','nsa','markup')),
  evidence jsonb not null default '{}'::jsonb,
  dollar_impact numeric(10,2)
);

-- ── Benchmarks (J's pipeline output) ─────────────────────────────────────
create table if not exists benchmarks (
  cpt text primary key,
  description text,
  medicare_rate numeric(10,2),
  fh_estimate numeric(10,2),          -- ALWAYS labeled "estimated" in UI (FAIR Health is paywalled)
  mrf_cash numeric(10,2),
  mrf_negotiated_median numeric(10,2),
  band_low numeric(10,2),
  band_high numeric(10,2),
  source_url text
);

-- ── Strategy & calls ─────────────────────────────────────────────────────
create table if not exists strategy_dossiers (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  target_entity text not null,
  route text not null check (route in ('provider','collections')),
  levers jsonb not null default '[]'::jsonb,            -- ordered, with entry/exit conditions + citation strings
  anchor numeric(10,2),
  target numeric(10,2),
  floor numeric(10,2),
  citations jsonb not null default '[]'::jsonb,
  prompt_compiled text,
  created_at timestamptz not null default now()
);

create table if not exists personas (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  style text not null,
  system_prompt text,
  hidden_params jsonb not null default '{}'::jsonb,     -- floor, concession map, quirks — never shown to the negotiator
  elevenlabs_agent_id text,
  twilio_number text
);

create table if not exists calls (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references cases(id) on delete cascade,
  dossier_id uuid references strategy_dossiers(id),
  counterparty text not null check (counterparty in ('agent','human')),
  persona_id uuid references personas(id),
  elevenlabs_conversation_id text,
  twilio_sid text,
  status text not null default 'queued',                -- queued|ringing|live|ended|failed
  recording_path text,
  started_at timestamptz,
  ended_at timestamptz
);

create table if not exists call_events (
  id bigint generated always as identity primary key,
  call_id uuid not null references calls(id) on delete cascade,
  ts timestamptz not null default now(),
  type text not null check (type in ('transcript','tool_call','state_change','quote','escalation')),
  payload jsonb not null default '{}'::jsonb
);

create table if not exists outcomes (
  id uuid primary key default gen_random_uuid(),
  call_id uuid not null references calls(id) on delete cascade,
  outcome_type text not null check (outcome_type in
    ('reduction','payment_plan','charity_app_initiated','callback','documented_decline')),
  original_amount numeric(10,2),
  final_amount numeric(10,2),
  reduction_pct numeric(5,2),
  winning_lever text,
  reference_number text,
  rep_name text,
  next_action text,
  evidence_event_ids bigint[] default '{}',
  honesty_audit jsonb                                    -- {passed: bool, checked_claims: [...]}
);

-- ── Realtime: the War Room subscribes to call_events ─────────────────────
alter publication supabase_realtime add table call_events;
alter publication supabase_realtime add table calls;

-- ── Storage buckets (documents + recordings) ─────────────────────────────
insert into storage.buckets (id, name, public) values ('documents','documents', false)
  on conflict (id) do nothing;
insert into storage.buckets (id, name, public) values ('recordings','recordings', false)
  on conflict (id) do nothing;
