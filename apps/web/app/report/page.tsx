"use client";

import { useEffect, useState } from "react";
import { getReport } from "../../lib/api";
import { money } from "../../lib/savings";
import { OUTCOME_LABELS } from "../../lib/types";
import type { CaseReport, ReportOutcome } from "../../lib/types";

// PRD §11 screens 5–6 — ranked outcomes across entities (rank key per §12,
// ranking done server-side), per-line billed vs. fair vs. achieved, and the
// plain-language recommendation. Renders GET /cases/demo/report.
export default function Report() {
  const [report, setReport] = useState<CaseReport | null>(null);
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");

  useEffect(() => {
    getReport("demo")
      .then((r) => {
        setReport(r);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, []);

  if (state === "loading") return <p className="todo">Loading your report…</p>;

  if (state === "error") {
    return (
      <p className="todo">
        Couldn&apos;t reach the API at :8000 — run <code>uvicorn app.main:app --reload --port 8000</code> in
        apps/api, then reload this page.
      </p>
    );
  }

  if (!report || report.outcomes.length === 0) {
    return (
      <div className="card" style={{ textAlign: "center", padding: "48px 32px" }}>
        <span className="pill pill-muted">Waiting on calls</span>
        <h2 style={{ margin: "16px 0 8px" }}>No completed calls yet</h2>
        <p style={{ color: "var(--text-secondary)", margin: "0 auto", maxWidth: 440, fontSize: 15 }}>
          Once the agent finishes negotiating, the ranked outcomes, final numbers, and our
          recommendation land here.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ marginTop: 16 }}>Your report</h1>
      <p style={{ color: "var(--text-secondary)", margin: "8px 0 24px" }}>
        Every outcome below is backed by call evidence — ranked best-first.
      </p>

      <h2 style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-tertiary)", marginBottom: 8 }}>
        Outcomes · ranked
      </h2>
      {report.outcomes.map((outcome, i) => (
        <OutcomeRow key={outcome.call_id ?? i} outcome={outcome} rank={i + 1} />
      ))}

      <h2 style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-tertiary)", margin: "24px 0 8px" }}>
        Line by line — billed vs. fair vs. achieved
      </h2>
      <div className="card" style={{ padding: "8px 24px", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr>
              {["CPT", "Billed", "Fair price", "Achieved"].map((h, i) => (
                <th
                  key={h}
                  style={{
                    textAlign: i === 0 ? "left" : "right",
                    padding: "10px 0",
                    fontSize: 12,
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    color: "var(--text-tertiary)",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.lines.map((line) => (
              <tr key={line.cpt}>
                <td className="mono-figure" style={{ padding: "10px 0", borderBottom: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                  {line.cpt}
                </td>
                <td className="mono-figure" style={{ padding: "10px 0", borderBottom: "1px solid var(--border)", textAlign: "right" }}>
                  {money(line.billed)}
                </td>
                <td className="mono-figure" style={{ padding: "10px 0", borderBottom: "1px solid var(--border)", textAlign: "right", color: "var(--text-secondary)" }}>
                  {money(line.fair)}
                </td>
                <td className="mono-figure" style={{ padding: "10px 0", borderBottom: "1px solid var(--border)", textAlign: "right", color: "var(--accent)", fontWeight: 600 }}>
                  {money(line.achieved)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-tertiary)", margin: "24px 0 8px" }}>
        Our recommendation
      </h2>
      <div className="argument-card">{report.recommendation}</div>
    </div>
  );
}

function OutcomeRow({ outcome, rank }: { outcome: ReportOutcome; rank: number }) {
  const label = outcome.outcome_type ? OUTCOME_LABELS[outcome.outcome_type] ?? outcome.outcome_type : "Outcome";
  const isWin = outcome.outcome_type === "reduction";
  const takeaways: [string, React.ReactNode][] = [];
  if (outcome.winning_lever) takeaways.push(["Winning lever", outcome.winning_lever]);
  if (outcome.reference_number)
    takeaways.push(["Reference #", <span className="mono-figure" key="ref">{outcome.reference_number}</span>]);
  if (outcome.original_amount != null && outcome.final_amount != null)
    takeaways.push([
      "Amount removed",
      <span className="mono-figure" style={{ color: "var(--accent)" }} key="amt">
        −{money(outcome.original_amount - outcome.final_amount)}
      </span>,
    ]);
  if (outcome.agreed_action) takeaways.push(["Agreed action", outcome.agreed_action]);
  if (outcome.next_action_date) takeaways.push(["Next action", outcome.next_action_date]);

  return (
    <div className="call-row">
      <div className="call-row-head">
        <div>
          <strong>#{rank} · {outcome.entity ?? (outcome.call_id ? `Call ${outcome.call_id.slice(0, 8)}` : "Call")}</strong>
          <div className="call-row-meta">
            {outcome.original_amount != null && outcome.final_amount != null ? (
              <>
                <span className="mono-figure">{money(outcome.original_amount)}</span> →{" "}
                <span className="mono-figure">{money(outcome.final_amount)}</span>
                {outcome.reduction_pct != null && <> · {Math.round(outcome.reduction_pct)}% off</>}
                {outcome.rep_name && <> · rep {outcome.rep_name}</>}
              </>
            ) : (
              outcome.rep_name && <>rep {outcome.rep_name}</>
            )}
          </div>
        </div>
        <span className={`pill ${isWin ? "pill-accent" : "pill-muted"}`}>{label}</span>
      </div>
      {takeaways.length > 0 && (
        <div className="call-takeaways">
          {takeaways.map(([dt, dd]) => (
            <div key={dt}><dt>{dt}</dt><dd>{dd}</dd></div>
          ))}
        </div>
      )}
    </div>
  );
}
