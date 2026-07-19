import type { CoverageStatus } from "../lib/types";
import { COVERAGE_LABELS } from "../lib/types";

// Per-line coverage badge (decision #12) — thin cross-payer data and codes
// absent from the hospital's own chargemaster get careful, non-accusatory
// phrasing, never "fraud" or "illegal." `full` and `professional_excluded`
// render nothing: a fully-benchmarked line needs no caveat, and a
// professional-fee line is legitimately billed by a separate entity, not a
// gap worth flagging.
export default function CoverageBadge({ coverage }: { coverage: CoverageStatus }) {
  if (coverage === "full") return null;

  const tone: Record<CoverageStatus, { cls: string; title: string }> = {
    full: { cls: "pill-muted", title: "" },
    thin: {
      cls: "pill-muted",
      title: "This code is in the hospital's chargemaster but too few payers report a negotiated rate to build a reliable band.",
    },
    absent_from_chargemaster: {
      cls: "pill-flag",
      title: "This code wasn't found in the hospital's own posted standard-charges file (45 CFR 180.20/180.50). Worth asking the hospital for the chargemaster reference — not an accusation.",
    },
    professional_excluded: {
      cls: "pill-muted",
      title: "Billed by a separate professional entity (e.g. the reading physician), not the facility — no chargemaster line is expected here.",
    },
    no_medicare: {
      cls: "pill-muted",
      title: "No Medicare rate is available for this code yet.",
    },
  };

  const { cls, title } = tone[coverage];
  return (
    <span className={`pill ${cls}`} title={title} style={{ fontSize: 11, whiteSpace: "nowrap" }}>
      {COVERAGE_LABELS[coverage]}
    </span>
  );
}
