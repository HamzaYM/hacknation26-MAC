// TS mirrors of contracts/*.schema.json and apps/api/app/models.py — the JSON
// Schemas are the source of truth. Change contracts FIRST, then models.py, then this file.

export type FlagType =
  | "duplicate" | "upcode" | "unbundle" | "phantom" | "eob_mismatch" | "nsa" | "markup";

export interface LineItem {
  cpt: string;
  description?: string;
  date_of_service?: string;
  units: number;
  billed_amount?: number | null;
  allowed_amount?: number | null;
  plan_paid?: number | null;
  patient_responsibility?: number | null;
  billing_entity?: string;
  dx_codes: string[];
}

export interface DerivedFlag {
  type: FlagType;
  cpt?: string | null;
  evidence: Record<string, unknown>;
  dollar_impact: number;
}

export type EntityKind =
  | "facility" | "er_physician_group" | "radiology" | "anesthesia" | "pathology" | "collections";

export interface Entity {
  name: string;
  kind: EntityKind;
  balance?: number | null;
  phone?: string;
}

export interface Bill {
  facility_name: string;
  nonprofit_status: boolean;
  statement_date?: string;
  due_date?: string;
  account_number: string;
  is_itemized: boolean;
  total_billed?: number | null;
  patient_balance?: number | null;
  line_items: LineItem[];
}

export interface Eob {
  claim_number?: string;
  patient_responsibility_total?: number | null;
  denial_codes: string[];
  line_items: LineItem[];
}

export interface JobSpec {
  case_id: string;
  patient: Record<string, unknown>;
  insurance: Record<string, unknown>;
  financial_profile: Record<string, unknown>;
  authorizations: Record<string, string>;
  bill: Bill;
  eob: Eob;
  derived_flags: DerivedFlag[];
  entities: Entity[];
}

export interface BenchmarkRow {
  cpt: string;
  description?: string;
  medicare_rate: number;
  fh_estimate?: number | null; // ALWAYS render as "estimated"
  mrf_cash?: number | null;
  mrf_negotiated_median?: number | null;
  band_low: number;
  band_high: number;
  source_url?: string;
}

export interface Lever {
  id: string;
  armed: boolean;
  armed_by?: string | null;
  citation?: string | null;
  dollar_ask?: number | null;
}

export interface StrategyDossier {
  case_id: string;
  target_entity: string;
  route: "provider" | "collections";
  levers: Lever[];
  anchor: number;
  target: number;
  floor: number;
  citations: string[];
  notes?: string;
}

// Matches the actual DB check constraint (supabase/migrations/0001_init.sql)
// — an earlier draft of this file invented a different enum
// (disclosure_given/lever_attempted/rung_advanced/...) that never matched
// the real schema. Payload shapes below are this file's own convention
// (call_events.payload is jsonb / freeform), not yet frozen with Hamza.
export type CallEventType =
  | "transcript" | "tool_call" | "state_change" | "quote" | "escalation"
  // question-guardrail + parking events (db.CALL_EVENT_TYPES, migrations 0004–0007)
  | "coverage_gap" | "read_back" | "topic_parked" | "callback_due" | "question_covered";

export interface CallEvent {
  id: number;
  call_id: string;
  ts: string;
  type: CallEventType;
  payload: Record<string, unknown>;
}

export type CallStatus = "queued" | "ringing" | "live" | "ended" | "failed";

export interface Call {
  id: string;
  case_id: string;
  counterparty: "agent" | "human";
  status: CallStatus;
  elevenlabs_conversation_id?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
}

// A `calls` row as the War Room multi-call overview reads it via PostgREST:
// the bare row plus the joined dossier's target entity (calls.dossier_id →
// strategy_dossiers). Client-side read shape, not a new contract.
export interface ActiveCall extends Call {
  dossier_id?: string | null;
  dossier?: { target_entity?: string | null; route?: string | null } | null;
}

export type OutcomeType =
  | "reduction" | "payment_plan" | "charity_app_initiated" | "callback" | "documented_decline";

export interface CallOutcome {
  call_id: string;
  outcome_type: OutcomeType;
  original_amount?: number | null;
  final_amount?: number | null;
  reduction_pct?: number | null;
  winning_lever?: string | null;
  reference_number?: string | null;
  rep_name?: string | null;
  agreed_action?: string | null;
  next_action_date?: string | null;
  decline_reason?: string | null;
  payment_plan_terms?: Record<string, unknown> | null;
  evidence_event_ids: number[];
}

// Provider ladder rung ids, in order — config/verticals/medical_bills.yaml `ladder.provider`.
export const PROVIDER_LADDER = [
  "open_and_hold_account",
  "reach_authority",
  "financial_assistance_screen",
  "line_item_disputes",
  "benchmark_anchor",
  "self_pay_prompt_pay_ask",
  "lump_sum_settlement",
  "payment_plan_fallback",
  "escalate_or_exit",
] as const;

export const LADDER_LABELS: Record<string, string> = {
  open_and_hold_account: "Request itemized bill & hold account",
  reach_authority: "Reach a supervisor or financial counselor",
  financial_assistance_screen: "Screen for charity care / financial assistance",
  line_item_disputes: "Dispute line-item errors",
  benchmark_anchor: "Cite Medicare & posted cash-price benchmark",
  self_pay_prompt_pay_ask: "Ask for self-pay / prompt-pay discount",
  lump_sum_settlement: "Offer lump-sum settlement",
  payment_plan_fallback: "Fall back to a payment plan",
  escalate_or_exit: "Escalate or exit with a documented outcome",
  // collections route — config/verticals/medical_bills.yaml `ladder.collections`
  diagnostic_questions: "Diagnostic questions: ownership, interest, floor",
  debt_validation_posture: "Set the debt-validation posture",
  lump_sum_anchor: "Anchor a lump-sum settlement",
  settle: "Settle with written paid-in-full terms",
  exit_with_written_confirmation: "Exit with written confirmation",
};

// Required questions per ladder rung — mirrors config/verticals/medical_bills.yaml
// `required_questions`. The engine's coverage gate won't let the call leave a rung
// until these are covered; the War Room coverage panel renders the current rung's
// list and flips each row to covered on a `question_covered` event (coral on a
// `coverage_gap`). Static mirror, same convention as LADDER_LABELS / PROVIDER_LADDER.
export const REQUIRED_QUESTIONS: Record<string, string[]> = {
  open_and_hold_account: ["account_hold_requested", "itemized_bill_status", "rep_name_captured"],
  financial_assistance_screen: ["fap_exists", "pauses_collections_while_pending"],
  diagnostic_questions: [
    "interest_accruing", "will_sue", "credit_bureau_reported",
    "debt_owned_or_bought", "predetermined_settlement_floor",
  ],
};

// Humanized labels for the coverage-question tags (fallback: underscores → spaces).
export const QUESTION_LABELS: Record<string, string> = {
  account_hold_requested: "Hold the account from collections",
  itemized_bill_status: "Itemized bill / UB-04 requested",
  rep_name_captured: "Rep's name captured",
  fap_exists: "Financial-assistance policy exists?",
  pauses_collections_while_pending: "Collections paused while pending?",
  interest_accruing: "Is interest still accruing?",
  will_sue: "Will they sue?",
  credit_bureau_reported: "Reported to the credit bureaus?",
  debt_owned_or_bought: "Do they own or buy the debt?",
  predetermined_settlement_floor: "Is there a settlement floor?",
};

// ---- API response envelopes (apps/api routers — frozen integration contract) ----

export interface LaunchedCall {
  call_id: string;
  entity: string;
  status: string;
}

export interface LaunchResponse {
  case_id: string;
  launched: LaunchedCall[];
}

export interface FlagsResponse {
  case_id: string;
  flags: DerivedFlag[];
}

export interface ConfirmResponse {
  case_id: string;
  status: string;
}

// GET /cases/{id}/report — outcomes arrive pre-ranked by the API (rank key per PRD §12).
export interface ReportLine {
  cpt: string;
  billed: number;
  fair: number;
  achieved: number;
}

// The call_events rows an outcome cites (its evidence_event_ids, ordered) —
// the report API returns them without id/call_id.
export interface EvidenceEvent {
  ts: string;
  type: CallEventType;
  payload: Record<string, unknown>;
}

// The CallOutcome fields the report surfaces per ranked entry; everything
// optional so the page renders defensively whatever subset the API includes.
export interface ReportOutcome {
  call_id?: string;
  entity?: string | null;
  outcome_type?: OutcomeType;
  original_amount?: number | null;
  final_amount?: number | null;
  reduction_pct?: number | null;
  winning_lever?: string | null;
  reference_number?: string | null;
  rep_name?: string | null;
  agreed_action?: string | null;
  next_action?: string | null;      // the outcomes table's free-text next step
  next_action_date?: string | null;
  resolved_at?: string | null;      // the call's ended_at — dates the paper trail
  evidence?: EvidenceEvent[];
  recording_url?: string | null;
}

// A parked/open topic the negotiator set aside to chase separately. A parallel
// builder is adding the open_items table + API; until it lands `open_items`
// arrives undefined and the case view derives everything from outcomes alone.
export interface OpenItem {
  entity?: string | null;
  lever?: string | null;
  detail?: string | null;
  amount_at_stake?: number | null;
  status?: "open" | "scheduled" | "resolved";
  next_attempt_at?: string | null;
  reference_number?: string | null;
  resolution_date?: string | null;
}

export interface CaseReport {
  outcomes: ReportOutcome[];
  lines: ReportLine[];
  recommendation: string;
  account_number?: string | null;   // the bill's own account number (copyable)
  claim_number?: string | null;     // the EOB claim number, when present
  open_items?: OpenItem[];          // optional — see OpenItem
}

export const OUTCOME_LABELS: Record<OutcomeType, string> = {
  reduction: "Reduction won",
  payment_plan: "Payment plan",
  charity_app_initiated: "Charity application started",
  callback: "Callback scheduled",
  documented_decline: "Declined · documented",
};

export const FLAG_LABELS: Record<FlagType, string> = {
  duplicate: "Duplicate charge",
  upcode: "Upcoded service level",
  unbundle: "Unbundled lab/procedure codes",
  phantom: "Charge for a service not rendered",
  eob_mismatch: "Bill doesn't match insurance EOB",
  nsa: "No Surprises Act protection",
  markup: "Priced above the fair benchmark",
};
