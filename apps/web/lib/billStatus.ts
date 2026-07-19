import type { Entity, EntityKind } from "./types";

export type BillStatus = "awaiting_you" | "in_progress" | "queued";

export const STATUS_META: Record<BillStatus, { label: string; pillClass: string; priority: number }> = {
  awaiting_you: { label: "Awaiting you", pillClass: "pill-danger", priority: 0 },
  in_progress: { label: "In progress", pillClass: "pill-warning", priority: 1 },
  queued: { label: "Queued", pillClass: "pill-muted", priority: 2 },
};

// TODO(Hamza): once calls/outcomes persist, this should read the real call
// status instead of being keyed off entity kind. For now: the facility has
// an active negotiation thread (in progress), the physician group is
// blocked on user authorization (awaiting you), collections hasn't been
// engaged yet (queued).
const STATUS_BY_KIND: Record<EntityKind, BillStatus> = {
  facility: "in_progress",
  er_physician_group: "awaiting_you",
  radiology: "awaiting_you",
  anesthesia: "awaiting_you",
  pathology: "awaiting_you",
  collections: "queued",
};

export function billStatus(entity: Pick<Entity, "kind">): BillStatus {
  return STATUS_BY_KIND[entity.kind];
}

export function sortByStatus<T extends { kind: EntityKind }>(entities: T[]): T[] {
  return [...entities].sort((a, b) => STATUS_META[billStatus(a)].priority - STATUS_META[billStatus(b)].priority);
}
