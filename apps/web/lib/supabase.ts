import { createClient } from "@supabase/supabase-js";

// Browser client (anon key only — service role stays server-side in FastAPI).
// The shared .env sets NEXT_PUBLIC_SUPABASE_URL with a /rest/v1/ suffix, but
// supabase-js wants the project base URL (it appends /rest/v1, /realtime/v1
// itself — the suffixed form silently breaks Realtime). Normalize here.
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://localhost:54321").replace(/\/rest\/v1\/?$/, "");

export const supabase = createClient(
  supabaseUrl,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "anon-key-not-set"
);
