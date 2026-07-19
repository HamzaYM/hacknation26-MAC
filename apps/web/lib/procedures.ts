import type { EntityKind } from "./types";

// A bill should read as "Provider — Procedure," not just a provider name —
// otherwise a user with several bills at the same hospital (or several
// hospitals) has no way to tell them apart at a glance. Derived from the
// fixture's diagnosis/CPT data (J06.9 = acute upper respiratory infection,
// seen via the ER) rather than invented; falls back to a generic label by
// entity kind if a specific procedure isn't known. TODO(J): once intake
// supports multiple distinct medical events, this should come from the
// JobSpec itself (a `procedure` or `chief_complaint` field per bill), not a
// frontend lookup table.
const KNOWN_PROCEDURE: Record<string, string> = {
  "Mercy General Hospital": "ER visit, acute respiratory infection",
  "Bay State Emergency Physicians": "ER visit, physician charges",
  "Meridian Recovery Services": "Lab panel (in collections)",
};

const FALLBACK_BY_KIND: Record<EntityKind, string> = {
  facility: "Facility charges",
  er_physician_group: "Physician charges",
  radiology: "Radiology charges",
  anesthesia: "Anesthesia charges",
  pathology: "Pathology charges",
  collections: "In collections",
};

export function procedureLabel(entityName: string, kind: EntityKind): string {
  return KNOWN_PROCEDURE[entityName] ?? FALLBACK_BY_KIND[kind];
}
