import type {
  BenchmarkReport,
  Call,
  CaseReport,
  ConfirmResponse,
  DerivedFlag,
  FlagsResponse,
  JobSpec,
  LaunchResponse,
  ScenarioLoadResponse,
  ScenarioSummary,
} from "./types";

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

// GET /cases/{id} — any case by id (fixture or a generalized new-bill case
// once WS3's case creation lands). Used by bills/[caseId] instead of always
// showing the demo case.
export async function getCase(caseId: string): Promise<JobSpec> {
  const res = await fetch(`${API_BASE}/cases/${caseId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /cases/${caseId} failed: ${res.status}`);
  return res.json();
}

// POST /cases — creates a fresh case for the new-bill upload flow. This
// endpoint is being built in parallel (WS3); until it lands, callers should
// catch and fall back to a client-generated id so the upload/parse calls
// still have somewhere to attach documents.
export async function createCase(): Promise<{ case_id: string }> {
  const res = await fetch(`${API_BASE}/cases`, { method: "POST" });
  if (!res.ok) throw new Error(`POST /cases failed: ${res.status}`);
  return res.json();
}

// ---- Scenarios (War Room picker, decision #11) ----
// GET /scenarios / POST /scenarios/{id}/load are WS3/WS4 deliverables landing
// in parallel worktrees. Until they merge, listScenarios() resolves to an
// empty array (never throws) so the picker shows its empty state instead of
// an error banner.
export async function listScenarios(): Promise<ScenarioSummary[]> {
  try {
    const res = await fetch(`${API_BASE}/scenarios`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : (data?.scenarios ?? []);
  } catch {
    return [];
  }
}

export async function loadScenario(scenarioId: string): Promise<ScenarioLoadResponse> {
  const res = await fetch(`${API_BASE}/scenarios/${scenarioId}/load`, { method: "POST" });
  if (!res.ok) throw new Error(`POST /scenarios/${scenarioId}/load failed: ${res.status}`);
  return res.json();
}

// GET /cases/{id}/benchmark_report — the per-line anchor set (decision #10)
// behind the multiples table + evidence toggle. WS2/WS3 deliverable; null
// (never throws) when unavailable so the dossier degrades to flags-only,
// same convention as getActionPlan/getReport below.
export async function getBenchmarkReport(caseId: string): Promise<BenchmarkReport | null> {
  try {
    const res = await fetch(`${API_BASE}/cases/${caseId}/benchmark_report`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
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

// ---- POST /cases/{id}/financial-profile (voice intake / manual card) ----
// The financial answers the documents can't provide. Only the fields the user
// answered are sent; the API overlays them onto the case's JobSpec (so /confirm
// reflects them) and returns the dossier `floor` derived from lump_sum_available.
export interface FinancialProfileInput {
  lump_sum_available?: number;
  monthly_max?: number;
  household_income?: number;
  household_size?: number;
}

export interface FinancialProfileResponse {
  case_id: string;
  financial_profile: Record<string, number>;
  floor: number | null;
  persisted: boolean;
}

export async function saveFinancialProfile(
  caseId: string,
  fields: FinancialProfileInput
): Promise<FinancialProfileResponse> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/financial-profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!res.ok) throw new Error(`POST /cases/${caseId}/financial-profile failed: ${res.status}`);
  return res.json();
}

// ---- GET /cases/{id}/action_plan (the pre-dial Action Plan for /confirm) ----
// `input` values are all engine-computed (numbers/dates/statutes); `copy` is the
// user-facing text — warm `claude -p` prose when honest, deterministic fallback
// otherwise. Every figure in `copy` is verbatim from `input` (server-side guard).

export interface ActionPlanCopy {
  headline: string;
  summary: string;
  flag_chips: { cpt?: string | null; label: string }[];
  savings_line: string;
  boost_panel?: { missing: string; copy: string }[];
  per_call_descriptions?: { entity: string; copy: string }[];
  timeline_copy: string;
  call_log_notes?: { call_ref?: string; copy: string }[];
  next_step_line: string;
  _source?: string;
}

export interface ActionPlanResponse {
  case_id: string;
  input: {
    balance: number;
    savings_estimate: { low: number | null; high: number | null; confidence: string };
    levers_armed: { id: string; citation: string | null; dollar_ask: number | null; armed_by: string }[];
    timeline: Record<string, string | null>;
    [k: string]: unknown;
  };
  copy: ActionPlanCopy;
}

// null = endpoint unavailable (the page falls back to flags-only rendering).
export async function getActionPlan(caseId: string): Promise<ActionPlanResponse | null> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/action_plan`, { cache: "no-store" });
  if (!res.ok) return null;
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
