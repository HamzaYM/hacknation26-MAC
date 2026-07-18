"use client";

import { useEffect, useState } from "react";
import { getReport } from "../../lib/api";
import { money } from "../../lib/savings";
import { OUTCOME_LABELS } from "../../lib/types";
import type { CaseReport, EvidenceEvent, ReportOutcome } from "../../lib/types";

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
      <EvidenceSection outcome={outcome} />
    </div>
  );
}

// Section sub-head style shared by the evidence blocks (matches the page's
// uppercase mini-headings; light-theme sibling of the War Room panel heads).
const evidenceHead: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  color: "var(--text-tertiary)",
  margin: "12px 0 6px",
};

// Expandable per-outcome evidence: the cited transcript lines + tool-call
// milestones (the call_events behind evidence_event_ids) and the call
// recording. Backend fields may not exist yet — everything treats absent
// as null and renders nothing rather than breaking.
function EvidenceSection({ outcome }: { outcome: ReportOutcome }) {
  const [open, setOpen] = useState(false);
  const evidence = outcome.evidence ?? [];
  const transcript = evidence.filter((e) => e.type === "transcript");
  const milestones = evidence.filter((e) => e.type !== "transcript");
  if (evidence.length === 0 && !outcome.recording_url) return null;

  return (
    <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          background: "none",
          border: "none",
          padding: 0,
          cursor: "pointer",
          fontFamily: "var(--font-body)",
          fontSize: 13,
          fontWeight: 600,
          color: "var(--accent)",
        }}
      >
        {open ? "▾" : "▸"} Evidence
        {evidence.length > 0 && <span style={{ color: "var(--text-tertiary)", fontWeight: 400 }}> · {evidence.length} cited event{evidence.length === 1 ? "" : "s"}</span>}
        {outcome.recording_url && <span style={{ color: "var(--text-tertiary)", fontWeight: 400 }}> · recording</span>}
      </button>

      {open && (
        <div>
          {transcript.length > 0 && (
            <>
              <div style={evidenceHead}>Cited transcript lines</div>
              <div
                style={{
                  background: "var(--bg-surface-muted)",
                  borderRadius: "var(--radius-input)",
                  padding: "var(--space-md)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  fontSize: 14,
                  lineHeight: 1.5,
                  maxHeight: 220,
                  overflowY: "auto",
                }}
              >
                {transcript.map((e, i) => (
                  <div key={`${e.ts}-${i}`}>
                    <span
                      className="mono"
                      style={{
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: "var(--accent)",
                        marginRight: 6,
                      }}
                    >
                      {String(e.payload?.speaker ?? "?")}
                    </span>
                    {String(e.payload?.text ?? "")}
                  </div>
                ))}
              </div>
            </>
          )}

          {milestones.length > 0 && (
            <>
              <div style={evidenceHead}>Call milestones</div>
              <div className="mono" style={{ fontSize: 12.5, display: "flex", flexDirection: "column", gap: 6 }}>
                {milestones.map((e, i) => (
                  <div key={`${e.ts}-${i}`}>
                    <span style={{ color: "var(--text-tertiary)", marginRight: 8 }}>
                      {new Date(e.ts).toLocaleTimeString()}
                    </span>
                    {milestoneLabel(e)}
                    {typeof e.payload?.result === "string" && (
                      <div style={{ color: "var(--text-secondary)", paddingLeft: 24 }}>→ {e.payload.result}</div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {evidence.length === 0 && (
            <p style={{ fontSize: 13, color: "var(--text-tertiary)", margin: "12px 0 0" }}>
              No cited call events for this outcome.
            </p>
          )}

          {outcome.recording_url && (
            <>
              <div style={evidenceHead}>Call recording</div>
              <audio controls src={outcome.recording_url} style={{ width: "100%" }} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function milestoneLabel(e: EvidenceEvent): string {
  const name = e.payload?.name;
  if (typeof name === "string" && name) return name;
  if (e.type === "quote" && e.payload?.amount != null) return `quote · $${Number(e.payload.amount).toLocaleString()}`;
  return e.type;
}
