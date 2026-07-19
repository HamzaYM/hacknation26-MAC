// ---- Regulatory deadline clocks, computed from the case's statement date ----
// Windows: FAP financial assistance (nonprofit hospitals, IRC §501(r): no
// extraordinary collection actions inside 240 days), GFE patient-provider
// dispute (No Surprises Act: 120 days from the bill date), FDCPA debt
// validation (30 days to demand the collector prove the debt — anchored to
// the statement date until real collector-contact dates persist).
//
// Extracted verbatim from app/bills/page.tsx so the Bill List and the case
// view render the exact same clocks off the exact same math.
const REGULATORY_CLOCKS = [
  { id: "fap", label: "FAP", days: 240, unlocks: "charity care application on the hospital bill" },
  { id: "gfe", label: "GFE dispute", days: 120, unlocks: "challenge charges above the good faith estimate" },
  { id: "fdcpa", label: "FDCPA validation", days: 30, unlocks: "force the collector to prove the debt" },
] as const;

const MS_PER_DAY = 86_400_000;

export function daysLeft(statementDate: string, windowDays: number): number {
  const start = new Date(`${statementDate}T00:00:00Z`).getTime();
  return Math.ceil((start + windowDays * MS_PER_DAY - Date.now()) / MS_PER_DAY);
}

export function DeadlineStrip({ statementDate }: { statementDate: string }) {
  const statementLabel = new Date(`${statementDate}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, margin: "0 0 24px" }}>
      <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: "0.02em", color: "var(--text-tertiary)" }}>
        Regulatory clocks · {statementLabel} statement
      </span>
      {REGULATORY_CLOCKS.map((clock) => {
        const left = daysLeft(statementDate, clock.days);
        const closing = left <= 30;
        return (
          <span
            key={clock.id}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-pill)",
              padding: "5px 12px",
              fontSize: 12.5,
            }}
          >
            <strong style={{ fontWeight: 600 }}>{clock.label}</strong>
            <span
              className="mono-figure"
              style={{ fontSize: 12, fontWeight: 600, color: closing ? "var(--flag)" : "var(--text-secondary)" }}
            >
              {left > 0 ? `${left}d left` : "closed"}
            </span>
            <span style={{ color: "var(--text-secondary)" }}>{clock.unlocks}</span>
          </span>
        );
      })}
    </div>
  );
}
