import { createClient } from "@supabase/supabase-js";

// Browser client (anon key only — service role stays server-side in FastAPI).
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://localhost:54321",
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "anon-key-not-set"
);
