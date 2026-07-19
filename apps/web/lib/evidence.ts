import type { DerivedFlag } from "./types";
import { money } from "./savings";

function firstDate(dates: unknown): string | null {
  if (Array.isArray(dates) && dates.length && typeof dates[0] === "string") return dates[0];
  return null;
}

function timesWord(n: number): string {
  return n === 2 ? "twice" : `${n} times`;
}

// One plain evidence line per finding, built only from the flag's own evidence
// payload (engine-computed) and the numbers already on the parse table, never
// invented — so a user can trace every finding back to a line on the bill.
export function evidenceLine(flag: DerivedFlag): string {
  const cpt = flag.cpt ? `CPT ${flag.cpt}` : "This charge";
  const e = flag.evidence ?? {};
  switch (flag.type) {
    case "duplicate": {
      const count = typeof e.count === "number" ? e.count : 2;
      const date = firstDate(e.dates);
      return `${cpt} billed ${timesWord(count)}${date ? ` on ${date}` : ""}.`;
    }
    case "upcode": {
      const supported = typeof e.supported === "string" ? e.supported : null;
      const dx = Array.isArray(e.dx_codes) ? (e.dx_codes as string[]).join(", ") : null;
      return `The diagnosis ${dx ? `(${dx}) ` : ""}supports a lower visit level${
        supported ? ` (${supported})` : ""
      } than what was billed.`;
    }
    case "unbundle": {
      const comp = typeof e.components_billed === "number" ? money(e.components_billed) : null;
      const bundled = typeof e.bundled === "number" ? money(e.bundled) : null;
      return `Component codes billed separately${comp ? ` at ${comp}` : ""}${
        bundled ? `; the bundled panel prices at ${bundled}` : ""
      }.`;
    }
    case "eob_mismatch": {
      const bill = typeof e.bill === "number" ? money(e.bill) : null;
      const eob = typeof e.eob === "number" ? money(e.eob) : null;
      return `Your bill shows ${bill ?? "more"}; your insurer's EOB shows ${eob ?? "less"} owed.`;
    }
    case "markup": {
      const billed = typeof e.billed === "number" ? money(e.billed) : null;
      const band = typeof e.band_high === "number" ? money(e.band_high) : null;
      return `Billed ${billed ?? "above the benchmark"}, over the fair benchmark top of ${
        band ?? "the market rate"
      }.`;
    }
    case "nsa":
      return "Out-of-network emergency charge protected by the No Surprises Act.";
    case "phantom":
      return "Charged for a service the records don't show was rendered.";
    default:
      return "See the finding detail for the evidence behind this.";
  }
}
