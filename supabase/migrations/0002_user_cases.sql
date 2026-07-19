-- The Negotiator — multi-user demo accounts
-- Each demo user (maya/dan/nina @hagglfor.me) owns one case. The API resolves
-- GET /cases/mine?email= against this column. Apply via scripts/seed_demo_users.py
-- (psycopg2, provision_supabase.py pattern) or the Supabase SQL editor.
-- NOTE: keep comments free of semicolons — the applier splits statements on them.

alter table cases add column if not exists owner_email text;

create index if not exists cases_owner_email_idx on cases (owner_email);
