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
export type CallEventType = "transcript" | "tool_call" | "state_change" | "quote" | "escalation";

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
