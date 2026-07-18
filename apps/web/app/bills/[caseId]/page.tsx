"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getDemoCase, launchCalls } from "../../../lib/api";
import { facilitySavings, money } from "../../../lib/savings";
import { procedureLabel } from "../../../lib/procedures";
import UploadCard from "../../../components/UploadCard";
import { FLAG_LABELS, LADDER_LABELS, PROVIDER_LADDER } from "../../../lib/types";
import type { JobSpec, DerivedFlag } from "../../../lib/types";

function findLineItem(spec: JobSpec, cpt?: string | null) {
  return spec.bill.line_items.find((li) => li.cpt === cpt);
}

// The state machine's current rung isn't exposed to the frontend yet (no GET
// endpoint — tools.py's state is per in-call session). This mirrors PRD §14's
// scripted demo position: duplicate conceded, now arguing the benchmark/NSA rung.
const DEMO_CURRENT_RUNG = "benchmark_anchor";

export default function BillDetail() {
  const [spec, setSpec] = useState<JobSpec | null>(null);
  const [tab, setTab] = useState<"diagnosis" | "plan" | "history" | "documents">("diagnosis");
  const [cashedIn, setCashedIn] = useState(false);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    getDemoCase().then(setSpec);
  }, []);

  if (!spec) return <p className="todo">Loading case…</p>;

  const savings = facilitySavings(spec);
  const barTotal = savings.percentSavedSoFar + savings.percentProjectedHigh;
  const achievedWidth = barTotal > 0 ? (savings.percentSavedSoFar / barTotal) * 100 : 0;
  const projectedWidth = barTotal > 0 ? (savings.percentProjectedHigh / barTotal) * 100 : 0;

  return (
    <div>
      <div className="user-strip">
        <a href="/bills" style={{ textDecoration: "none", color: "inherit" }}>Bills</a>
        <span>›</span>
        <span>{spec.bill.facility_name}</span>
      </div>

      <div className="bill-header" style={{ marginTop: 8 }}>
        <div>
          <h1>{spec.bill.facility_name}</h1>
          <div style={{ color: "var(--text-secondary)", fontSize: 15, marginBottom: 8 }}>
            {procedureLabel(spec.bill.facility_name, "facility")}
          </div>
          <span className={`pill ${cashedIn ? "pill-muted" : "pill-accent"}`}>
            {cashedIn ? "Locked in — no further calls" : "In progress"}
          </span>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="balance-new mono-figure">{money(savings.currentBalance)}</div>
          <div className="balance-old mono-figure">{money(savings.originalBalance)}</div>
        </div>
      </div>

      <div className="stat-pair">
        <div className="stat">
          <div className="stat-num accent">{money(savings.savedSoFar)} · {savings.percentSavedSoFar}%</div>
          <div className="stat-cap">Saved so far — confirmed</div>
        </div>
        <div className="stat">
          <div className="stat-num">{money(savings.projectedLow)}–{money(savings.projectedHigh)}</div>
          <div className="stat-cap">Projected additional · {savings.percentProjectedLow}–{savings.percentProjectedHigh}% more if all findings land</div>
        </div>
      </div>

      <div className="savings-bar-wrap" style={{ marginBottom: 8 }}>
        <div className="savings-bar">
          <div className="achieved" style={{ width: `${achievedWidth}%` }} />
          <div className="projected" style={{ width: `${projectedWidth}%` }} />
        </div>
        <div className="savings-legend">
          <span><span className="dot achieved" />Locked in</span>
          <span><span className="dot projected" />Still possible</span>
        </div>
      </div>

      {!cashedIn && !confirming && (
        <button className="btn btn-secondary" onClick={() => setConfirming(true)}>
          I&apos;m done — cash in {money(savings.savedSoFar)} ({savings.percentSavedSoFar}%) now →
        </button>
      )}
      {confirming && (
        <div className="cash-in-confirm">
          Lock in <strong>{money(savings.savedSoFar)}</strong> saved and stop further calls on this bill? You&apos;ll
          give up the {money(savings.projectedLow)}–{money(savings.projectedHigh)} still possible if we keep going.
          <div className="row">
            <button className="btn btn-primary" onClick={() => { setCashedIn(true); setConfirming(false); }}>
              Yes, lock it in
            </button>
            <button className="btn btn-secondary" onClick={() => setConfirming(false)}>Keep negotiating</button>
          </div>
        </div>
      )}

      <div className="tabs">
        <button className={`tab ${tab === "diagnosis" ? "active" : ""}`} onClick={() => setTab("diagnosis")}>Diagnosis</button>
        <button className={`tab ${tab === "plan" ? "active" : ""}`} onClick={() => setTab("plan")}>Plan</button>
        <button className={`tab ${tab === "history" ? "active" : ""}`} onClick={() => setTab("history")}>Call History</button>
        <button className={`tab ${tab === "documents" ? "active" : ""}`} onClick={() => setTab("documents")}>Documents</button>
      </div>

      {tab === "diagnosis" && <DiagnosisTab spec={spec} />}
      {tab === "plan" && <PlanTab spec={spec} cashedIn={cashedIn} />}
      {tab === "history" && <HistoryTab spec={spec} />}
      {tab === "documents" && <DocumentsTab spec={spec} />}
    </div>
  );
}

function DiagnosisTab({ spec }: { spec: JobSpec }) {
  const hasNsa = spec.derived_flags.some((f) => f.type === "nsa");
  const eobMismatch = spec.derived_flags.find((f) => f.type === "eob_mismatch");
  const markupFlag = spec.derived_flags.find((f) => f.type === "markup");
  const totalFlagged = spec.derived_flags
    .filter((f) => f.type !== "eob_mismatch")
    .reduce((sum, f) => sum + f.dollar_impact, 0);

  return (
    <div>
      <h2 style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-tertiary)", marginBottom: 8 }}>
        The central argument
      </h2>
      <div className="argument-card">
        {hasNsa && <>You&apos;re likely protected under the <strong>No Surprises Act</strong>, </>}
        there&apos;s a billing error inflating this bill by <strong>{money(eobMismatch?.dollar_impact)}</strong>
        {markupFlag && <>, and {spec.bill.facility_name} is charging roughly 200% of the fair benchmark price</>}
        {!markupFlag && <>, and several line items are priced well above the Medicare and posted-cash-price benchmark</>}.
      </div>

      <h2 style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-tertiary)", margin: "24px 0 8px", display: "flex", justifyContent: "space-between" }}>
        <span>{spec.derived_flags.length} findings on this bill</span>
        <span>Total flagged: <span className="mono-figure" style={{ color: "var(--flag)" }}>{money(totalFlagged)}</span></span>
      </h2>

      {spec.derived_flags.map((flag, i) => (
        <Finding key={i} flag={flag} spec={spec} />
      ))}
    </div>
  );
}

function Finding({ flag, spec }: { flag: DerivedFlag; spec: JobSpec }) {
  const li = findLineItem(spec, flag.cpt);
  return (
    <div className="finding-card">
      <div className="finding-head">
        <div>
          {flag.cpt && <span className="cpt">CPT {flag.cpt} · </span>}
          <strong>{FLAG_LABELS[flag.type]}</strong>
          {li?.description && <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{li.description}</div>}
        </div>
        <span className="impact">+{money(flag.dollar_impact)}</span>
      </div>
      <div className="finding-evidence">
        <strong style={{ color: "var(--text-tertiary)", fontSize: 12, textTransform: "uppercase" }}>Evidence</strong>
        <div style={{ marginTop: 4 }}>
          {flag.type === "duplicate" && "Itemized bill lists this code twice on the same date of service — a clean duplicate."}
          {flag.type === "upcode" && `Diagnosis and documentation support a lower visit level (${(flag.evidence.supported as string) ?? "—"}) than what was billed.`}
          {flag.type === "unbundle" && `Component tests total ${money(flag.evidence.components_billed as number)}; the bundled panel code prices at ${money(flag.evidence.bundled as number)}.`}
          {flag.type === "eob_mismatch" && `Your bill shows ${money(flag.evidence.bill as number)}; your insurer's EOB shows ${money(flag.evidence.eob as number)} owed.`}
          {(flag.type === "nsa" || flag.type === "markup" || flag.type === "phantom") && "See dossier citation for this line."}
        </div>
      </div>
    </div>
  );
}

function PlanTab({ spec, cashedIn }: { spec: JobSpec; cashedIn: boolean }) {
  const router = useRouter();
  const [launching, setLaunching] = useState(false);
  const [launchedCallId, setLaunchedCallId] = useState<string | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const currentIndex = PROVIDER_LADDER.indexOf(DEMO_CURRENT_RUNG as (typeof PROVIDER_LADDER)[number]);

  async function startCalls() {
    setLaunching(true);
    setLaunchError(null);
    try {
      const { launched } = await launchCalls(spec.case_id, { simulate: true });
      const first = launched[0];
      if (!first) throw new Error("no calls launched");
      setLaunchedCallId(first.call_id);
      router.push(`/warroom?call_id=${first.call_id}`);
    } catch {
      setLaunching(false);
      setLaunchError(
        "Couldn't start the calls — the API at :8000 didn't answer. Nothing was dialed; try again in a moment."
      );
    }
  }

  if (cashedIn) {
    return (
      <p className="todo" style={{ borderColor: "var(--border)", background: "var(--bg-surface-muted)", color: "var(--text-secondary)" }}>
        You cashed in your savings on this bill — no further calls are scheduled. Reopen negotiation anytime from
        the bill header above.
      </p>
    );
  }

  return (
    <div>
      <div className="live-strip">
        <div>
          <span className="pill pill-muted">Next scheduled call</span>
          <div style={{ marginTop: 6, fontWeight: 600 }}>
            Continuing the {LADDER_LABELS[PROVIDER_LADDER[currentIndex]]?.toLowerCase()} step with {spec.bill.facility_name}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn btn-primary" onClick={startCalls} disabled={launching} style={launching ? { opacity: 0.7 } : undefined}>
            {launching ? "Dialing…" : "Start the calls"}
          </button>
          <a
            href={launchedCallId ? `/warroom?call_id=${launchedCallId}` : "/warroom"}
            className="btn btn-secondary"
            style={{ textDecoration: "none" }}
          >
            Open War Room →
          </a>
        </div>
      </div>
      {launchError && (
        <p className="todo" style={{ marginBottom: 16 }}>{launchError}</p>
      )}

      <div className="stepper">
        {PROVIDER_LADDER.map((rung, i) => {
          const state = i < currentIndex ? "done" : i === currentIndex ? "active" : "future";
          return (
            <div className={`step ${state}`} key={rung}>
              <div className="step-dot">{state === "done" ? "✓" : i + 1}</div>
              <div>
                <div className="step-label">{LADDER_LABELS[rung]}</div>
                {state === "done" && rung === "line_item_disputes" && (
                  <div className="step-won">−$412 won</div>
                )}
                {state === "active" && (
                  <div className="step-detail">
                    Agent is arguing Medicare pays $438 for these codes and the facility&apos;s own posted
                    cash price is $1,890 — is this negotiable?
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HistoryTab({ spec }: { spec: JobSpec }) {
  // Static demo content — call_events/call_outcome persistence is a Hamza TODO
  // (see apps/api/app/routers/tools.py log_quote/log_event/end_call_summary).
  return (
    <div>
      <div className="call-row">
        <div className="call-row-head">
          <div>
            <strong>{spec.bill.facility_name} · billing dept</strong>
            <div className="call-row-meta">Mar 18, 2026 · 14m 20s · rep Denise</div>
          </div>
          <span className="pill pill-accent">Partial win</span>
        </div>
        <div className="call-takeaways">
          <div><dt>Winning lever</dt><dd>Duplicate charge, EOB-backed</dd></div>
          <div><dt>Reference #</dt><dd className="mono-figure">MG-2026-04471</dd></div>
          <div><dt>Amount removed</dt><dd className="mono-figure" style={{ color: "var(--accent)" }}>−$412.00</dd></div>
          <div><dt>Next action</dt><dd>Supervisor callback · Tue 10a</dd></div>
        </div>
      </div>
      <div className="call-row">
        <div className="call-row-head">
          <div>
            <strong>Carolina Emergency Physicians</strong>
            <div className="call-row-meta">Mar 16, 2026 · 2m 03s</div>
          </div>
          <span className="pill pill-muted">Callback scheduled</span>
        </div>
      </div>
      <div className="call-row">
        <div className="call-row-head">
          <div>
            <strong>{spec.bill.facility_name} · records</strong>
            <div className="call-row-meta">Mar 12, 2026 · 6m 41s</div>
          </div>
          <span className="pill pill-muted">Itemized bill requested</span>
        </div>
      </div>
    </div>
  );
}

function DocumentsTab({ spec }: { spec: JobSpec }) {
  // Real files aren't wired to Supabase Storage yet (bucket layout in
  // negotiator-intake-data-schema.md — `documents/`, TODO(J)/TODO(Hamza)).
  // What IS real here: every metadata field (account #, claim #, statement/
  // due dates, line-item count) is pulled straight from the parsed JobSpec,
  // not invented — this is what the intake step actually extracted.
  const docs = [
    {
      title: "Itemized bill",
      type: "PDF",
      meta: [
        ["Account #", spec.bill.account_number],
        ["Statement date", spec.bill.statement_date ?? "—"],
        ["Due date", spec.bill.due_date ?? "—"],
        ["Line items", String(spec.bill.line_items.length)],
      ],
    },
    {
      title: "Explanation of Benefits (EOB)",
      type: "PDF",
      meta: [
        ["Claim #", spec.eob.claim_number ?? "—"],
        ["Patient responsibility", money(spec.eob.patient_responsibility_total)],
        ["Denial codes", spec.eob.denial_codes.length ? spec.eob.denial_codes.join(", ") : "None"],
      ],
    },
  ];

  return (
    <div>
      {docs.map((doc) => (
        <div className="document-card" key={doc.title}>
          <div className="document-icon">📄</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600 }}>{doc.title}</div>
            <dl className="document-meta">
              {doc.meta.map(([k, v]) => (
                <div key={k}><dt>{k}</dt><dd className="mono-figure">{v}</dd></div>
              ))}
            </dl>
          </div>
          <button className="btn btn-secondary" disabled>
            View {doc.type}
          </button>
        </div>
      ))}
      <div style={{ marginTop: 16 }}>
        <UploadCard
          title="Add another document"
          hint="Drag a PDF or photo — a follow-up letter, a second EOB, anything relevant to this bill"
        />
      </div>
      <p className="todo" style={{ marginTop: 16 }}>
        File preview/download isn&apos;t wired to Supabase Storage yet — this tab shows the real extracted
        metadata from your intake, but the &quot;View&quot; buttons are placeholders until Storage lands.
      </p>
    </div>
  );
}
