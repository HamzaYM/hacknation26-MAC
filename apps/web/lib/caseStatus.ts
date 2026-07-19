// Buckets the case's outcomes (+ optional parked open items) into the three
// fixed sections the case view renders — Resolved / In progress / Scheduled.
// Convention mirrors lib/billStatus.ts: a small pure derivation + a META map.
//
// Grouping is by ENTITY, not by call: every call the negotiator placed to one
// party collapses into a single card whose paper trail lists the calls. That
// keeps the top level to a handful of cards instead of a flat ranked list.
//
// Renders gracefully when open-items data is absent: a parallel builder is
// adding the open_items table + API, so `report.open_items` may be undefined.
// When it lands, contract per item:
//   { entity?, lever, detail, amount_at_stake, status: open|scheduled|resolved,
//     next_attempt_at, reference_number, resolution_date }
import type { CaseReport, EntityKind, JobSpec, OpenItem, ReportOutcome } from "./types";

export type CaseBucket = "resolved" | "in_progress" | "scheduled";

export const BUCKET_ORDER: CaseBucket[] = ["resolved", "in_progress", "scheduled"];

export const BUCKET_META: Record<
  CaseBucket,
  { label: string; explainer: string; pillClass: string }
> = {
  resolved: {
    label: "Resolved",
    explainer: "Confirmed in writing, nothing left to do.",
    pillClass: "pill-accent",
  },
  in_progress: {
    label: "In progress",
    explainer: "We're actively chasing these.",
    pillClass: "pill-flag",
  },
  scheduled: {
    label: "Scheduled",
    explainer: "Next in the queue, not yet contacted.",
    pillClass: "pill-muted",
  },
};

export interface CaseItem {
  entity: string;
  kind?: EntityKind;
  bucket: CaseBucket;
  billed: number | null; // original balance in play for this party
  achieved: number | null; // settled amount, when a settlement was reached
  savedAmount: number | null; // billed − achieved, when both are known
  nextStep: string | null; // the bold NextStepLine (non-resolved cards)
  settlementNote: string | null; // the soft "you still owe" line on resolved cards
  repName: string | null;
  winningLever: string | null;
  referenceNumber: string | null; // only when it looks like a real identifier
  resolvedAt: string | null;
  nextAttemptAt: string | null;
  outcomes: ReportOutcome[]; // every outcome for this party, newest first
  openItems: OpenItem[];
}

// A reference/account/claim number worth showing has at least one digit — this
// filters rep names that leaked into the field (e.g. a callback logged "Bob").
export function looksLikeReference(value?: string | null): boolean {
  return !!value && /\d/.test(value);
}

// A pending (non-settlement) outcome, best-first — decides an entity's headline
// next step when several calls are still open on the same party.
const PENDING_PRIORITY: Record<string, number> = {
  charity_app_initiated: 0,
  payment_plan: 1,
  callback: 2,
  documented_decline: 3,
};

function isSettlement(o: ReportOutcome): boolean {
  return o.final_amount != null && (o.outcome_type === "reduction" || o.outcome_type === "payment_plan");
}

function isPending(o: ReportOutcome): boolean {
  return !isSettlement(o) && o.outcome_type != null && o.outcome_type in PENDING_PRIORITY;
}

function nextStepLabel(o: ReportOutcome): string {
  switch (o.outcome_type) {
    case "charity_app_initiated":
      return o.next_action?.trim() || "Submit the financial-assistance application";
    case "payment_plan":
      return "Review the payment plan on the table";
    case "callback":
      return "Take the scheduled callback";
    case "documented_decline":
      return "Book a follow-up with a supervisor";
    default:
      return o.next_action?.trim() || "We keep working this one";
  }
}

function isFuture(iso?: string | null): boolean {
  if (!iso) return false;
  const t = new Date(iso).getTime();
  return Number.isFinite(t) && t > Date.now();
}

/** Group outcomes + open items by entity and assign each party a bucket. */
export function buildCaseItems(report: CaseReport, spec?: JobSpec | null): CaseItem[] {
  const balanceByName = new Map<string, { balance: number | null; kind: EntityKind }>();
  for (const e of spec?.entities ?? []) balanceByName.set(e.name, { balance: e.balance ?? null, kind: e.kind });

  const openItems = report.open_items ?? [];
  const byEntity = new Map<string, { outcomes: ReportOutcome[]; open: OpenItem[] }>();
  const bucketFor = (name: string) => {
    if (!byEntity.has(name)) byEntity.set(name, { outcomes: [], open: [] });
    return byEntity.get(name)!;
  };
  for (const o of report.outcomes) bucketFor(o.entity || "The provider").outcomes.push(o);
  for (const oi of openItems) if (oi.entity) bucketFor(oi.entity).open.push(oi);

  const items: CaseItem[] = [];
  for (const [entity, { outcomes, open }] of byEntity) {
    // newest first so the paper trail reads top-down and the headline uses the
    // freshest facts
    const ordered = [...outcomes].sort(
      (a, b) => (b.resolved_at ? Date.parse(b.resolved_at) : 0) - (a.resolved_at ? Date.parse(a.resolved_at) : 0)
    );
    const settlement = ordered.find(isSettlement) ?? null;
    const pending = [...ordered.filter(isPending)].sort(
      (a, b) => (PENDING_PRIORITY[a.outcome_type ?? ""] ?? 9) - (PENDING_PRIORITY[b.outcome_type ?? ""] ?? 9)
    );
    const headlinePending = pending[0] ?? null;

    const hasOpenWork = pending.length > 0 || open.some((oi) => oi.status === "open");
    const scheduledOnly =
      ordered.length === 0 &&
      (open.every((oi) => oi.status === "scheduled") && open.some((oi) => isFuture(oi.next_attempt_at)));

    let bucket: CaseBucket;
    if (scheduledOnly) bucket = "scheduled";
    else if (settlement && !hasOpenWork) bucket = "resolved";
    else bucket = "in_progress";

    const meta = balanceByName.get(entity);
    const billed =
      meta?.balance ??
      settlement?.original_amount ??
      headlinePending?.original_amount ??
      ordered.find((o) => o.original_amount != null)?.original_amount ??
      null;
    const achieved = settlement?.final_amount ?? null;
    const savedAmount = billed != null && achieved != null ? billed - achieved : null;

    const primary = bucket === "resolved" ? settlement : headlinePending ?? settlement;
    const refCandidate = primary?.reference_number ?? open.find((oi) => oi.reference_number)?.reference_number ?? null;

    items.push({
      entity,
      kind: meta?.kind,
      bucket,
      billed,
      achieved,
      savedAmount,
      nextStep: bucket === "resolved" ? null : headlinePending ? nextStepLabel(headlinePending) : null,
      settlementNote:
        bucket === "resolved" && settlement?.next_action ? settlement.next_action.trim() : null,
      repName: primary?.rep_name ?? null,
      winningLever: settlement?.winning_lever ?? headlinePending?.winning_lever ?? null,
      referenceNumber: looksLikeReference(refCandidate) ? refCandidate : null,
      resolvedAt: settlement?.resolved_at ?? primary?.resolved_at ?? null,
      nextAttemptAt: open.find((oi) => isFuture(oi.next_attempt_at))?.next_attempt_at ?? null,
      outcomes: ordered,
      openItems: open,
    });
  }

  // Section order drives visual order; within a section, bigger money first.
  const order: Record<CaseBucket, number> = { resolved: 0, in_progress: 1, scheduled: 2 };
  return items.sort(
    (a, b) => order[a.bucket] - order[b.bucket] || (b.billed ?? 0) - (a.billed ?? 0)
  );
}

export interface CaseCounts {
  resolved: number;
  in_progress: number;
  scheduled: number;
  lockedIn: number; // dollars confirmed off the bill so far
}

export function caseCounts(items: CaseItem[]): CaseCounts {
  return {
    resolved: items.filter((i) => i.bucket === "resolved").length,
    in_progress: items.filter((i) => i.bucket === "in_progress").length,
    scheduled: items.filter((i) => i.bucket === "scheduled").length,
    lockedIn: items
      .filter((i) => i.bucket === "resolved" && i.savedAmount != null)
      .reduce((sum, i) => sum + (i.savedAmount ?? 0), 0),
  };
}

function count(n: number, noun: string): string {
  return `${n === 0 ? "No" : n} ${noun}${n === 1 ? "" : "s"}`;
}

/** One plain-language line answering "what's going on with my file?". */
export function statusSentence(items: CaseItem[], counts: CaseCounts): string {
  if (items.length === 0) return "No calls have wrapped up yet — outcomes land here the moment they do.";
  const parts: string[] = [];
  if (counts.resolved > 0) parts.push(`${count(counts.resolved, "item")} resolved`);
  if (counts.in_progress > 0) parts.push(`${counts.in_progress} still in progress`);
  if (counts.scheduled > 0) parts.push(`${counts.scheduled} scheduled`);
  let sentence = parts.length ? capitalize(joinClauses(parts)) + "." : "";

  const callback = items.find((i) => i.bucket !== "resolved" && i.outcomes.some((o) => o.outcome_type === "callback"));
  if (callback) sentence += ` A callback is lined up with ${callback.entity}.`;
  return sentence.trim();
}

function joinClauses(parts: string[]): string {
  if (parts.length <= 1) return parts.join("");
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}`;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
