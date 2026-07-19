"use client";

import { useEffect, useState } from "react";
import { getMyCase, getReport } from "../../lib/api";
import { useSession } from "../../lib/auth";
import { money } from "../../lib/savings";
import {
  BUCKET_META,
  BUCKET_ORDER,
  buildCaseItems,
  caseCounts,
  looksLikeReference,
  statusSentence,
  type CaseBucket,
  type CaseItem,
} from "../../lib/caseStatus";
import { DeadlineStrip } from "../../components/DeadlineStrip";
import ReferenceChip from "../../components/ReferenceChip";
import { LADDER_LABELS, OUTCOME_LABELS } from "../../lib/types";
import type { CaseReport, JobSpec, ReportOutcome } from "../../lib/types";

// The case file — the patient's whole negotiation in one calm surface. Not a
// ranked list: three fixed sections (Resolved / In progress / Scheduled), one
// card per party, a bold next step on everything still open, and the paper
// trail (dated calls, reference numbers, audio) behind progressive disclosure.
// Redesign flagged for Susy's review — tokens/components per design-system.md.
export default function Report() {
  const session = useSession();
  const email = session?.user?.email;
  const [spec, setSpec] = useState<JobSpec | null>(null);
  const [report, setReport] = useState<CaseReport | null>(null);
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    getMyCase(email ?? undefined)
      .then(async (s) => {
        if (cancelled) return;
        setSpec(s);
        const r = await getReport(s.case_id);
        if (cancelled) return;
        setReport(r);
        setState("ready");
      })
      .catch(() => !cancelled && setState("error"));
    return () => {
      cancelled = true;
    };
  }, [email]);

  if (state === "loading") return <p className="todo">Loading your case…</p>;

  if (state === "error") {
    return (
      <p className="todo">
        Couldn&apos;t reach the API. Run <code>uvicorn app.main:app --reload --port 8000</code> in
        apps/api, then reload this page.
      </p>
    );
  }

  const patientName = (spec?.patient?.legal_name as string) ?? "–";
  const facility = spec?.bill.facility_name;
  const items = report ? buildCaseItems(report, spec) : [];
  const counts = caseCounts(items);

  return (
    <div>
      <h1 style={{ marginTop: 16 }}>Your case</h1>
      <p style={{ color: "var(--text-secondary)", margin: "6px 0 20px", fontSize: 15 }}>
        Everything we&apos;ve done on {facility ? `your ${facility} bill` : "your bill"}, in one place —
        newest first, with the paper trail behind every number.
      </p>

      <CaseHeader
        patientName={patientName}
        account={report?.account_number}
        claim={report?.claim_number}
        lockedIn={counts.lockedIn}
        billCount={items.length}
      />

      {spec?.bill.statement_date && <DeadlineStrip statementDate={spec.bill.statement_date} />}

      {items.length === 0 ? (
        <EmptyCase />
      ) : (
        <>
          <StatusSummaryBar items={items} counts={counts} />
          {BUCKET_ORDER.map((bucket) => (
            <CaseSection key={bucket} bucket={bucket} items={items.filter((i) => i.bucket === bucket)} />
          ))}
          {report && report.lines.length > 0 && <LineByLine report={report} />}
        </>
      )}
    </div>
  );
}

// ---- Case header: identity (user-strip + copyable case numbers) + a demoted
// savings figure. The big hero from the Bill List is deliberately shrunk here —
// the case file leads with status, not a celebration number.
function CaseHeader({
  patientName,
  account,
  claim,
  lockedIn,
  billCount,
}: {
  patientName: string;
  account?: string | null;
  claim?: string | null;
  lockedIn: number;
  billCount: number;
}) {
  return (
    <header className="case-header">
      <div className="case-header-id">
        <span className="user-strip" style={{ padding: 0 }}>
          <span className="avatar">{patientName.charAt(0) || "?"}</span>
          <span>
            <strong>{patientName}</strong>
          </span>
          <span>· Boston, MA</span>
        </span>
        <div className="case-refs">
          {looksLikeReference(account) && <ReferenceChip label="Account #" value={account!} />}
          {looksLikeReference(claim) && <ReferenceChip label="Claim #" value={claim!} />}
        </div>
      </div>
      <div className="case-savings">
        <span className="case-savings-figure mono-figure">{money(lockedIn)}</span>
        <span className="case-savings-cap">
          locked in so far{billCount > 0 ? ` · ${billCount} ${billCount === 1 ? "party" : "parties"}` : ""}
        </span>
      </div>
    </header>
  );
}

function StatusSummaryBar({ items, counts }: { items: CaseItem[]; counts: ReturnType<typeof caseCounts> }) {
  return (
    <div className="status-bar">
      <div className="status-pills">
        <span className="pill pill-accent">{counts.resolved} resolved</span>
        <span className="pill pill-flag">{counts.in_progress} in progress</span>
        <span className="pill pill-muted">{counts.scheduled} scheduled</span>
      </div>
      <p className="status-sentence">{statusSentence(items, counts)}</p>
    </div>
  );
}

function CaseSection({ bucket, items }: { bucket: CaseBucket; items: CaseItem[] }) {
  const meta = BUCKET_META[bucket];
  return (
    <section className="case-section">
      <div className="case-section-head">
        <h2 className="case-section-title">{meta.label}</h2>
        <span className="case-section-count">{items.length}</span>
        <span className="case-section-explainer">{meta.explainer}</span>
      </div>
      {items.length === 0 ? (
        <p className="case-section-empty">
          {bucket === "resolved"
            ? "Nothing settled yet — the first win lands here."
            : bucket === "scheduled"
              ? "Nothing queued right now. Re-attempts appear here with their call time."
              : "Nothing in flight right now."}
        </p>
      ) : (
        <div className="case-grid">
          {items.map((item) => (
            <CaseItemCard key={item.entity} item={item} />
          ))}
        </div>
      )}
    </section>
  );
}

// Lever ids the negotiator reports aren't all ladder rungs — humanize the ones
// that show up as winning levers, prettify the rest.
const LEVER_LABELS: Record<string, string> = {
  lump_sum_today: "Lump-sum settlement",
  statutory_501r: "§501(r) charity care",
  ...LADDER_LABELS,
};
function leverLabel(id: string): string {
  return LEVER_LABELS[id] ?? id.replace(/_/g, " ");
}

function fmtDateTime(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return null;
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function CaseItemCard({ item }: { item: CaseItem }) {
  const meta = BUCKET_META[item.bucket];
  const resolved = item.bucket === "resolved";
  const callCount = item.outcomes.length;

  return (
    <article className="case-card">
      <div className="case-card-top">
        <h3 className="case-card-entity">{item.entity}</h3>
        <span className={`pill ${meta.pillClass}`}>{meta.label}</span>
      </div>

      <div className="case-card-amount">
        {item.achieved != null && item.billed != null ? (
          <>
            <span className="amt-old mono-figure">{money(item.billed)}</span>
            <span className="amt-arrow" aria-hidden>
              →
            </span>
            <span className="amt-new mono-figure">{money(item.achieved)}</span>
            {item.savedAmount != null && item.savedAmount > 0 && (
              <span className="amt-saved mono-figure">−{money(item.savedAmount)}</span>
            )}
          </>
        ) : (
          <>
            <span className="amt-standalone mono-figure">{money(item.billed)}</span>
            <span className="amt-standalone-cap">at stake</span>
          </>
        )}
      </div>

      {item.nextStep && (
        <div className="next-step">
          <span className="next-step-label">Next</span>
          <span className="next-step-text">
            {item.nextStep}
            {fmtDateTime(item.nextAttemptAt) && <> · {fmtDateTime(item.nextAttemptAt)}</>}
          </span>
        </div>
      )}

      {resolved && item.settlementNote && (
        <div className="settle-note">
          You pay <strong className="mono-figure">{money(item.achieved)}</strong> — {item.settlementNote}
        </div>
      )}

      <div className="case-card-facts">
        {item.repName && (
          <span className="fact">
            <span className="fact-key">Rep</span> {item.repName}
          </span>
        )}
        {item.winningLever && (
          <span className="fact">
            <span className="fact-key">Won on</span> {leverLabel(item.winningLever)}
          </span>
        )}
        {resolved && fmtDateTime(item.resolvedAt) && (
          <span className="fact">
            <span className="fact-key">Settled</span> {fmtDateTime(item.resolvedAt)}
          </span>
        )}
        {item.referenceNumber && <ReferenceChip label="Ref" value={item.referenceNumber} />}
      </div>

      {(callCount > 0 || item.openItems.length > 0) && <PaperTrail item={item} />}
    </article>
  );
}

// Progressive disclosure — the top level stays a card; the dated call history,
// reference numbers, transcript, and audio live behind this expander.
function PaperTrail({ item }: { item: CaseItem }) {
  const [open, setOpen] = useState(false);
  const callCount = item.outcomes.length;

  return (
    <div className="paper-trail">
      <button className="paper-trail-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? "▾" : "▸"} Paper trail
        <span className="paper-trail-count">
          {callCount} call{callCount === 1 ? "" : "s"}
          {item.openItems.length > 0 && ` · ${item.openItems.length} parked`}
        </span>
      </button>
      {open && (
        <div className="stepper" style={{ marginTop: "var(--space-md)" }}>
          {item.outcomes.map((o, i) => (
            <CallStep key={o.call_id ?? i} outcome={o} />
          ))}
          {item.openItems.map((oi, i) => (
            <div className="step future" key={`open-${i}`}>
              <span className="step-dot">–</span>
              <div>
                <div className="step-label">Parked · {oi.lever ? leverLabel(oi.lever) : "open item"}</div>
                {oi.detail && <div className="step-detail">{oi.detail}</div>}
                {oi.next_attempt_at && (
                  <div className="step-detail">Next attempt {fmtDateTime(oi.next_attempt_at)}</div>
                )}
                {looksLikeReference(oi.reference_number) && (
                  <div style={{ marginTop: 6 }}>
                    <ReferenceChip label="Ref" value={oi.reference_number!} />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function stepGlyph(o: ReportOutcome): { glyph: string; cls: string } {
  if (o.final_amount != null) return { glyph: "✓", cls: "done" };
  if (o.outcome_type === "documented_decline") return { glyph: "–", cls: "future" };
  return { glyph: "•", cls: "active" };
}

function CallStep({ outcome }: { outcome: ReportOutcome }) {
  const [showTranscript, setShowTranscript] = useState(false);
  const { glyph, cls } = stepGlyph(outcome);
  const date = fmtDateTime(outcome.resolved_at);
  const label = outcome.outcome_type ? OUTCOME_LABELS[outcome.outcome_type] ?? outcome.outcome_type : "Call";
  const transcript = (outcome.evidence ?? []).filter((e) => e.type === "transcript");

  return (
    <div className={`step ${cls}`}>
      <span className="step-dot">{glyph}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="step-label">
          {date ?? "Call"}
          {outcome.rep_name && <span className="step-rep"> · {outcome.rep_name}</span>}
        </div>
        <div className="step-detail">
          <strong style={{ color: "var(--text-primary)" }}>{label}.</strong>{" "}
          {outcome.final_amount != null && outcome.original_amount != null && (
            <>
              <span className="mono-figure">{money(outcome.original_amount)}</span> →{" "}
              <span className="mono-figure" style={{ color: "var(--accent)" }}>
                {money(outcome.final_amount)}
              </span>
              {outcome.winning_lever && <> on {leverLabel(outcome.winning_lever)}</>}.{" "}
            </>
          )}
          {outcome.final_amount == null && outcome.next_action && <>{outcome.next_action}</>}
        </div>

        {looksLikeReference(outcome.reference_number) && (
          <div style={{ marginTop: 8 }}>
            <ReferenceChip label="Ref" value={outcome.reference_number!} />
          </div>
        )}

        {outcome.recording_url && (
          <audio controls src={outcome.recording_url} style={{ width: "100%", marginTop: 10, height: 34 }} />
        )}

        {transcript.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <button className="mini-toggle" onClick={() => setShowTranscript((s) => !s)}>
              {showTranscript ? "Hide" : "Show"} transcript · {transcript.length} line
              {transcript.length === 1 ? "" : "s"}
            </button>
            {showTranscript && (
              <div className="transcript-box">
                {transcript.map((e, i) => (
                  <div key={`${e.ts}-${i}`}>
                    <span className="transcript-speaker mono">{String(e.payload?.speaker ?? "?")}</span>
                    {String(e.payload?.text ?? "")}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// The per-CPT billed vs. fair vs. achieved math, kept but demoted behind an
// expander so the top of the case file stays calm.
function LineByLine({ report }: { report: CaseReport }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="case-section">
      <button className="paper-trail-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? "▾" : "▸"} The full line-by-line math
        <span className="paper-trail-count">{report.lines.length} codes</span>
      </button>
      {open && (
        <div className="card" style={{ padding: "8px 24px", overflowX: "auto", marginTop: "var(--space-md)" }}>
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
      )}
    </section>
  );
}

function EmptyCase() {
  return (
    <div className="card" style={{ textAlign: "center", padding: "48px 32px" }}>
      <span className="pill pill-muted">Waiting on calls</span>
      <h2 style={{ margin: "16px 0 8px" }}>No completed calls yet</h2>
      <p style={{ color: "var(--text-secondary)", margin: "0 auto", maxWidth: 440, fontSize: 15 }}>
        Once the agent finishes negotiating, every outcome lands here — sorted into what&apos;s resolved,
        in progress, and scheduled, each with its own paper trail.
      </p>
    </div>
  );
}
