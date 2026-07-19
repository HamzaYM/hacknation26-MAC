-- The Negotiator — chargemaster data foundation (WS1, generalized pipeline)
-- Owner: J. Apply via `supabase db push` (or run in the Supabase SQL editor).
--
-- `chargemaster_charges` (881,668 rows) and `chargemaster_coverage` (3 rows)
-- already exist LIVE in Supabase — created ad hoc during data ingestion,
-- with zero migration backing them (see audit/schema-db.md finding #5: "This
-- is a real risk... silent data loss on any fresh environment"). This
-- migration formalizes the schema that is already live so a fresh
-- environment (`supabase db push` on an empty project) gets the same table
-- shape, even though it won't get the 881,668 rows themselves (those are
-- loaded by scripts/stage_chargemaster.py from the source SQLite DB).
--
-- `medicare_rates` is new: staged by scripts/fetch_medicare.py from real CMS
-- PFS/OPPS/CLFS data (see data/seed/medicare_rates.json for the committed,
-- provenance-carrying rows this table mirrors).
--
-- Apply-safe / idempotent: every statement is `if not exists` — safe to run
-- against the already-populated live project without touching existing rows.

create table if not exists chargemaster_charges (
  id bigserial primary key,
  hospital_name text not null,
  hospital_ein text,
  ccn text,
  system text,
  city text,
  state text,
  file_url text,
  setting text,
  code text not null,
  code_type text not null,  -- CPT | HCPCS | DRG | MS-DRG | CDM | RC | LOCAL | TRIS-DRG
  description text,
  gross_charge numeric,
  cash_price numeric,
  payer_name text,
  plan_name text,
  negotiated_dollar numeric,
  negotiated_percentage numeric,
  negotiated_algorithm text,
  methodology text,
  min_negotiated numeric,
  max_negotiated numeric,
  estimated_amount numeric,  -- 100% null in the source data as of this build; kept for schema parity
  notes text
);

-- Stage-3 (gross charge/cash price) + stage-4 (plan-specific rate) lookups filter
-- on hospital+code+code_type before joining payer/plan; stage-5 (cross-payer band)
-- groups by code+payer. These three indexes cover the lookup layer's query shapes
-- (apps/api/app/engine/lookup_sqlite.py / lookup_supabase.py).
create index if not exists idx_chargemaster_charges_hospital_code
  on chargemaster_charges (hospital_name, code);
create index if not exists idx_chargemaster_charges_code
  on chargemaster_charges (code);
create index if not exists idx_chargemaster_charges_code_payer
  on chargemaster_charges (code, payer_name);
create index if not exists idx_chargemaster_charges_code_type
  on chargemaster_charges (code_type);

create table if not exists chargemaster_coverage (
  hospital_name text primary key,
  rows integer,
  status text,
  error text
);

-- Real Medicare rates (professional/facility/global), computed by plain code
-- from CMS PFS RVU+GPCI / OPPS Addendum B / CLFS files — see
-- scripts/fetch_medicare.py header for the formula and source URLs, and
-- data/seed/medicare_rates.json for the exact committed rows this mirrors.
-- One row per (code, code_type, component); upserted by
-- scripts/fetch_medicare.py --stage-supabase.
create table if not exists medicare_rates (
  id bigserial primary key,
  code text not null,
  code_type text not null default 'CPT',
  component text not null,  -- professional | facility | global
  value numeric(12,2) not null,
  formula text,
  source text,
  source_url text,
  file_version text,
  locality text,
  label text,
  version text,
  updated_at timestamptz not null default now(),
  unique (code, code_type, component)
);

create index if not exists idx_medicare_rates_code on medicare_rates (code);
