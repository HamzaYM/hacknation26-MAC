import type { Entity, JobSpec } from "./types";

export interface BillSavings {
  originalBalance: number;
  savedSoFar: number;
  currentBalance: number;
  projectedLow: number;
  projectedHigh: number;
  percentSavedSoFar: number;
  percentProjectedLow: number;
  percentProjectedHigh: number;
}

function pct(amount: number, base: number) {
  return base > 0 ? Math.round((amount / base) * 100) : 0;
}

// Facility bill has real derived_flags. "Won" = the one call already reflected
// in the (hardcoded, demo-only) Call History tab — the duplicate concession.
// eob_mismatch is excluded: it's the same $412 as the duplicate, not a second
// recoverable amount (evidence, not an independent finding). Everything else
// still open is "projected," shown as a range since these are candidates, not
// confirmed wins yet (PRD calls upcode a "candidate" specifically).
// TODO(Hamza): once call_outcome persists, savedSoFar should sum real
// outcome.final_amount deltas instead of this hardcoded demo value.
export function facilitySavings(spec: JobSpec): BillSavings {
  const originalBalance = spec.bill.patient_balance ?? 0;
  const savedSoFar = spec.derived_flags.find((f) => f.type === "duplicate")?.dollar_impact ?? 0;
  const openFlags = spec.derived_flags.filter((f) => f.type !== "duplicate" && f.type !== "eob_mismatch");
  const openTotal = openFlags.reduce((sum, f) => sum + f.dollar_impact, 0);

  const projectedLow = Math.round(openTotal * 0.5);
  const projectedHigh = Math.round(openTotal);
  const currentBalance = originalBalance - savedSoFar;

  return {
    originalBalance,
    savedSoFar,
    currentBalance,
    projectedLow,
    projectedHigh,
    percentSavedSoFar: pct(savedSoFar, originalBalance),
    percentProjectedLow: pct(projectedLow, originalBalance),
    percentProjectedHigh: pct(projectedHigh, originalBalance),
  };
}

// No per-entity flag data exists yet for non-facility entities (TODO Hamza —
// derived_flags aren't attributed to a billing_entity in the current engine
// output). These are typical ranges by entity kind, not case-specific
// findings — labeled as such wherever rendered, never as a confirmed number.
const TYPICAL_RANGE: Record<string, [number, number]> = {
  er_physician_group: [0.15, 0.35],
  radiology: [0.15, 0.35],
  anesthesia: [0.15, 0.35],
  pathology: [0.15, 0.35],
  collections: [0.25, 0.5],
  facility: [0.15, 0.35],
};

export function entitySavings(entity: Entity): BillSavings {
  const originalBalance = entity.balance ?? 0;
  const [lowPct, highPct] = TYPICAL_RANGE[entity.kind] ?? [0.15, 0.35];
  return {
    originalBalance,
    savedSoFar: 0,
    currentBalance: originalBalance,
    projectedLow: Math.round(originalBalance * lowPct),
    projectedHigh: Math.round(originalBalance * highPct),
    percentSavedSoFar: 0,
    percentProjectedLow: Math.round(lowPct * 100),
    percentProjectedHigh: Math.round(highPct * 100),
  };
}

export function money(n?: number | null) {
  if (n == null) return "—";
  return `$${Math.round(n).toLocaleString("en-US")}`;
}
