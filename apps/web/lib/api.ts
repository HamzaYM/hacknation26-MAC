import type { Call, JobSpec } from "./types";

// Same-origin in the browser (proxied by next.config.mjs rewrites → :8000,
// avoids CORS entirely); server components/scripts can override via env.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export async function getDemoCase(): Promise<JobSpec> {
  const res = await fetch(`${API_BASE}/cases/demo`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /cases/demo failed: ${res.status}`);
  return res.json();
}

// apps/api/app/routers/calls.py's GET /calls/{id} is still a stub
// ({"call_id":..., "status":"stub"}) — this will start returning the real
// `calls` row (status/counterparty/started_at/…) once Hamza wires Supabase.
export async function getCall(callId: string): Promise<Call> {
  const res = await fetch(`${API_BASE}/calls/${callId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /calls/${callId} failed: ${res.status}`);
  return res.json();
}
