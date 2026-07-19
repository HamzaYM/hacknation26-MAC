import type { Call, CaseReport, ConfirmResponse, DerivedFlag, FlagsResponse, JobSpec, LaunchResponse } from "./types";

// Same-origin in the browser (proxied by next.config.mjs rewrites → :8000,
// avoids CORS entirely); server components/scripts can override via env.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export async function getDemoCase(): Promise<JobSpec> {
  const res = await fetch(`${API_BASE}/cases/demo`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /cases/demo failed: ${res.status}`);
  return res.json();
}

// The logged-in user's case, resolved by email (cases.owner_email). Without
// an email — or for an unknown one — the API falls back to Maya's demo case.
export async function getMyCase(email?: string): Promise<JobSpec> {
  const qs = email ? `?email=${encodeURIComponent(email)}` : "";
  const res = await fetch(`${API_BASE}/cases/mine${qs}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /cases/mine failed: ${res.status}`);
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

// simulate=true runs the simulated call driver per launched call (demo mode).
export async function launchCalls(caseId: string, opts?: { simulate?: boolean }): Promise<LaunchResponse> {
  const res = await fetch(`${API_BASE}/calls/launch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: caseId, simulate: opts?.simulate }),
  });
  if (!res.ok) throw new Error(`POST /calls/launch failed: ${res.status}`);
  return res.json();
}

export async function confirmCase(caseId: string): Promise<ConfirmResponse> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/confirm`, { method: "POST" });
  if (!res.ok) throw new Error(`POST /cases/${caseId}/confirm failed: ${res.status}`);
  return res.json();
}

export async function getFlags(caseId: string): Promise<FlagsResponse> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/flags`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /cases/${caseId}/flags failed: ${res.status}`);
  return res.json();
}

// ---- POST /documents/parse (frozen intake contract — backend may land after this) ----

export interface ParsedLineItem {
  cpt: string;
  description?: string;
  date_of_service?: string;
  billed_amount?: number | null;
  dx_codes?: string[];
}

export interface ParsedDocument {
  line_items: ParsedLineItem[];
  total_billed?: number | null;
  // Bills report patient_balance; EOBs report patient_responsibility_total.
  patient_balance?: number | null;
  patient_responsibility_total?: number | null;
}

export interface ReconciliationMismatch {
  cpt: string;
  field: string;
  parsed: unknown;
  expected: unknown;
}

export interface Reconciliation {
  verdict: "exact" | "partial" | "failed";
  matches: number;
  mismatches: ReconciliationMismatch[];
}

export interface ParseDocumentResponse {
  document_id: string;
  storage_path: string;
  parsed: ParsedDocument;
  reconciliation: Reconciliation;
  flags: DerivedFlag[];
}

// Omitting caseId lets the API default to the demo case.
export async function parseDocument(
  file: File,
  kind: "bill" | "eob",
  caseId?: string
): Promise<ParseDocumentResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  if (caseId) form.append("case_id", caseId);
  const res = await fetch(`${API_BASE}/documents/parse`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`POST /documents/parse failed: ${res.status}`);
  return res.json();
}

// null = no report yet (404 — no completed calls); throws on other failures.
export async function getReport(caseId: string): Promise<CaseReport | null> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/report`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET /cases/${caseId}/report failed: ${res.status}`);
  return res.json();
}
