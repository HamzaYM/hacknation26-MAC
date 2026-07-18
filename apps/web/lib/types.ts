// TS mirrors of contracts/*.schema.json — the JSON Schemas are the source of truth.
// Change contracts FIRST, then apps/api/app/models.py, then this file.

export type FlagType =
  | "duplicate" | "upcode" | "unbundle" | "phantom" | "eob_mismatch" | "nsa" | "markup";

export interface LineItem {
  cpt: string;
  description?: string;
  date_of_service?: string;
  units?: number;
  billed_amount?: number | null;
  allowed_amount?: number | null;
  plan_paid?: number | null;
  patient_responsibility?: number | null;
  billing_entity?: string;
}

export interface DerivedFlag {
  type: FlagType;
  cpt?: string | null;
  evidence?: Record<string, unknown>;
  dollar_impact: number;
}

export interface Entity {
  name: string;
  kind: "facility" | "er_physician_group" | "radiology" | "anesthesia" | "pathology" | "collections";
  balance?: number;
  phone?: string;
}

export interface JobSpec {
  case_id: string;
  patient: Record<string, unknown>;
  insurance: Record<string, unknown>;
  financial_profile: Record<string, unknown>;
  authorizations: Record<string, string>;
  bill: {
    facility_name: string;
    nonprofit_status: boolean;
    account_number: string;
    total_billed?: number;
    patient_balance?: number;
    line_items: LineItem[];
  };
  eob: { claim_number?: string; patient_responsibility_total?: number; line_items: LineItem[] };
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
}

export type CallEventType =
  | "disclosure_given" | "lever_attempted" | "rung_advanced"
  | "quote_logged" | "escalation" | "outcome" | "transcript_chunk";

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
}
