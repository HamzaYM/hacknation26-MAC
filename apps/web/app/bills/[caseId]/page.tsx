"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getBenchmarkReport, getCase, launchCalls } from "../../../lib/api";
import { subscribeToCallsForCase } from "../../../lib/realtime";
import { facilitySavings, money } from "../../../lib/savings";
import { procedureLabel } from "../../../lib/procedures";
import UploadCard from "../../../components/UploadCard";
import ActionItemCard from "../../../components/ActionItemCard";
import MultiplesTable from "../../../components/MultiplesTable";
import { itemsForEntity } from "../../../lib/actionItems";
import { FLAG_LABELS, LADDER_LABELS, PROVIDER_LADDER } from "../../../lib/types";
import type { JobSpec, DerivedFlag, Call, BenchmarkReport } from "../../../lib/types";

function findLineItem(spec: JobSpec, cpt?: string | null) {
  return spec.bill.line_items.find((li) => li.cpt === cpt);
}

// The state machine's current rung isn't exposed to the frontend yet (no GET
// endpoint — tools.py's state is per in-call session). This mirrors PRD §14's
// scripted demo position: duplicate conceded, now arguing the benchmark/NSA rung.
const DEMO_CURRENT_RUNG = "benchmark_anchor";

// "Cash in" doesn't mean "silently stop." What actually needs to happen:
// the agent finishes the CURRENT thread (it never leaves a lever half-pulled
// or a verbal concession unconfirmed), gets the already-won reduction
// confirmed in writing with a reference number — the same structured-outcome
// discipline every other call in this product follows — and only then does
// the bill move to "Settled." This wrap-up state simulates that call; a real
// implementation would trigger it via POST /calls/launch with a
// wrap_up_and_confirm objective rather than just flipping a status flag.
const WRAP_UP_REF = "MG-CONF-8842";

export default function BillDetail() {
  const params = useParams<{ caseId: string }>();
  const caseId = params.caseId;
  const [spec, setSpec] = useState<JobSpec | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [tab, setTab] = useState<"diagnosis" | "plan" | "history" | "documents" | "actions">("diagnosis");
  const [cashedIn, setCashedIn] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [wrappingUp, setWrappingUp] = useState(false);
  // Bill-scoped completion state — separate from the aggregate /action-items
  // page's own state (no shared store yet; TODO(Hamza) once this persists
  // server-side, both views should read/write the same source of truth).
  const [completedActionIds, setCompletedActionIds] = useState<Set<string>>(new Set());
  // Real state, not a guess — only true when a `calls` row for this case is
  // actually ringing/live (via the Realtime subscription below), so the
  // live-call card only shows when a call genuinely is. "Start the calls" on
  // the Plan tab (POST /calls/launch) is what makes that happen.
  const [liveCall, setLiveCall] = useState<Call | null>(null);
  // Per-line multiples table data (decision #10) — a generalized-pipeline
  // deliverable landing in a parallel worktree; null while unavailable, and
  // the Diagnosis tab degrades to flags-only (no crash, no broken UI).
  const [benchmarkReport, setBenchmarkReport] = useState<BenchmarkReport | null>(null);

  useEffect(() => {
    if (!caseId) return;
    setSpec(null);
    setLoadError(false);
    getCase(caseId)
      .then(setSpec)
      .catch(() => setLoadError(true));
    getBenchmarkReport(caseId).then(setBenchmarkReport);
  }, [caseId]);

  useEffect(() => {
    if (!spec) return;
    const unsubscribe = subscribeToCallsForCase(spec.case_id, (call) => {
      setLiveCall(call.status === "live" || call.status === "ringing" ? call : null);
    });
    return () => {
      unsubscribe();
    };
  }, [spec]);

  useEffect(() => {
    if (!wrappingUp) return;
    const t = setTimeout(() => {
      setWrappingUp(false);
      setCashedIn(true);
    }, 2400);
    return () => clearTimeout(t);
  }, [wrappingUp]);

  if (loadError) {
    return (
      <p className="todo">
        Couldn&apos;t load this case (<span className="mono-figure">{caseId}</span>). Either the API at :8000
        isn&apos;t running, or this case hasn&apos;t been created there yet. Go back to{" "}
        <a href="/bills">your bills</a> and try again.
      </p>
    );
  }
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
          <span className={`pill ${cashedIn ? "pill-muted" : wrappingUp ? "pill-flag" : "pill-accent"}`}>
            {cashedIn ? "Settled · confirmed in writing" : wrappingUp ? "Confirming your savings…" : "In progress"}
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
          <div className="stat-cap">Saved so far · confirmed</div>
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

      {!cashedIn && !confirming && !wrappingUp && (
        <button className="btn btn-secondary" onClick={() => setConfirming(true)}>
          I&apos;m done, cash in {money(savings.savedSoFar)} ({savings.percentSavedSoFar}%) now →
        </button>
      )}
      {confirming && (
        <div className="cash-in-confirm">
          Lock in <strong>{money(savings.savedSoFar)}</strong> saved and stop pursuing more on this bill? You&apos;ll
          give up the {money(savings.projectedLow)}–{money(savings.projectedHigh)} still possible if we keep going.
          We&apos;ll place one final call to confirm the reduction already won in writing before closing this out.
          <div className="row">
            <button className="btn btn-primary" onClick={() => { setWrappingUp(true); setConfirming(false); }}>
              Yes, wrap it up
            </button>
            <button className="btn btn-secondary" onClick={() => setConfirming(false)}>Keep negotiating</button>
          </div>
        </div>
      )}
      {wrappingUp && (
        <div className="cash-in-confirm">
          <span className="live-dot"><span className="dot" />CONFIRMING</span>
          <div style={{ marginTop: 6 }}>
            Placing a final call to {spec.bill.facility_name} to confirm your {money(savings.savedSoFar)} reduction
            in writing and get a reference number…
          </div>
        </div>
      )}

      {(() => {
        const pendingActions = itemsForEntity(spec.bill.facility_name).filter((i) => !completedActionIds.has(i.id));
        return (
          <>
            <div className="tabs">
              <button className={`tab ${tab === "diagnosis" ? "active" : ""}`} onClick={() => setTab("diagnosis")}>Diagnosis</button>
              <button className={`tab ${tab === "plan" ? "active" : ""}`} onClick={() => setTab("plan")}>Plan</button>
              <button className={`tab ${tab === "history" ? "active" : ""}`} onClick={() => setTab("history")}>Call History</button>
              <button className={`tab ${tab === "actions" ? "active" : ""}`} onClick={() => setTab("actions")}>
                Action Items{pendingActions.length > 0 && ` (${pendingActions.length})`}
              </button>
              <button className={`tab ${tab === "documents" ? "active" : ""}`} onClick={() => setTab("documents")}>Documents</button>
            </div>

            {tab === "diagnosis" && <DiagnosisTab spec={spec} benchmarkReport={benchmarkReport} />}
            {tab === "plan" && <PlanTab spec={spec} cashedIn={cashedIn} wrappingUp={wrappingUp} liveCall={liveCall} />}
            {tab === "history" && <HistoryTab spec={spec} cashedIn={cashedIn} />}
            {tab === "actions" && (
              <ActionsTab
                items={pendingActions}
                onComplete={(id) => setCompletedActionIds((prev) => new Set(prev).add(id))}
              />
            )}
            {tab === "documents" && <DocumentsTab spec={spec} cashedIn={cashedIn} />}
          </>
        );
      })()}
    </div>
  );
}

function ActionsTab({ items, onComplete }: { items: ReturnType<typeof itemsForEntity>; onComplete: (id: string) => void }) {
  if (items.length === 0) {
    return (
      <p className="todo" style={{ borderColor: "var(--border)", background: "var(--bg-surface-muted)", color: "var(--text-secondary)" }}>
        Nothing outstanding on this bill right now.
      </p>
    );
  }
  return (
    <div>
      {items.map((item) => (
        <ActionItemCard key={item.id} item={item} onComplete={() => onComplete(item.id)} compact />
      ))}
    </div>
  );
}

function DiagnosisTab({ spec, benchmarkReport }: { spec: JobSpec; benchmarkReport: BenchmarkReport | null }) {
  const hasNsa = spec.derived_flags.some((f) => f.type === "nsa" || f.type === "nsa_balance_billing");
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

      {benchmarkReport && (
        <>
          <h2 style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-tertiary)", margin: "24px 0 8px" }}>
            Per-line benchmarks
          </h2>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12 }}>
            Every line against Medicare, a fair band, and what&apos;s available in {benchmarkReport.hospital}&apos;s
            posted rates. Lines priced above the RAND overcharge threshold are highlighted.
          </p>
          <MultiplesTable report={benchmarkReport} />
        </>
      )}
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
          {flag.type === "duplicate" && "Itemized bill lists this code twice on the same date of service. A clean duplicate."}
          {flag.type === "upcode" && `Diagnosis and documentation support a lower visit level (${(flag.evidence.supported as string) ?? "–"}) than what was billed.`}
          {flag.type === "unbundle" && `Component tests total ${money(flag.evidence.components_billed as number)}; the bundled panel code prices at ${money(flag.evidence.bundled as number)}.`}
          {flag.type === "eob_mismatch" && `Your bill shows ${money(flag.evidence.bill as number)}; your insurer's EOB shows ${money(flag.evidence.eob as number)} owed.`}
          {flag.type === "absent_from_chargemaster" &&
            "Not found on the hospital's own posted standard charges for this code — worth asking for the chargemaster reference; not an accusation of wrongdoing."}
          {["nsa", "nsa_balance_billing", "markup", "phantom", "denial", "units_error"].includes(flag.type) &&
            "See dossier citation for this line."}
        </div>
      </div>
    </div>
  );
}

function PlanTab({
  spec,
  cashedIn,
  wrappingUp,
  liveCall,
}: {
  spec: JobSpec;
  cashedIn: boolean;
  wrappingUp: boolean;
  liveCall: Call | null;
}) {
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
        "Couldn't start the calls. The API at :8000 didn't answer. Nothing was dialed; try again in a moment."
      );
    }
  }

  if (cashedIn) {
    return (
      <p className="todo" style={{ borderColor: "var(--border)", background: "var(--bg-surface-muted)", color: "var(--text-secondary)" }}>
        Settled. Your {money(facilitySavings(spec).savedSoFar)} reduction was confirmed in writing,
        reference <span className="mono-figure">{WRAP_UP_REF}</span>. See Call History for the wrap-up call, and
        Documents for the confirmation letter. Reopen negotiation anytime from the bill header above.
      </p>
    );
  }

  if (wrappingUp) {
    return (
      <p className="todo" style={{ borderColor: "var(--border)", background: "var(--bg-surface-muted)", color: "var(--text-secondary)" }}>
        Wrapping up: placing a final call to get your {money(facilitySavings(spec).savedSoFar)} reduction confirmed
        in writing before this bill closes out.
      </p>
    );
  }

  return (
    <div>
      {liveCall ? (
        // Honest live-call gating: this strip only appears when a `calls` row
        // for this case is actually ringing/live (Realtime subscription).
        <div className="live-strip">
          <div>
            <span className="live-dot"><span className="dot" />LIVE CALL</span>
            <div style={{ marginTop: 6, fontWeight: 600 }}>
              Continuing the {LADDER_LABELS[PROVIDER_LADDER[currentIndex]]?.toLowerCase()} step with {spec.bill.facility_name}
            </div>
          </div>
          <a href={`/warroom?call_id=${liveCall.id}`} className="btn btn-secondary" style={{ textDecoration: "none" }}>
            Watch &amp; listen live →
          </a>
        </div>
      ) : (
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
      )}
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
                    cash price is $2,633. Is this negotiable?
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

function HistoryTab({ spec, cashedIn }: { spec: JobSpec; cashedIn: boolean }) {
  // Static demo content — call_events/call_outcome persistence is a Hamza TODO
  // (see apps/api/app/routers/tools.py log_quote/log_event/end_call_summary).
  const savings = facilitySavings(spec);
  return (
    <div>
      {cashedIn && (
        <div className="call-row">
          <div className="call-row-head">
            <div>
              <strong>{spec.bill.facility_name} · wrap-up call</strong>
              <div className="call-row-meta">Just now · confirmation call</div>
            </div>
            <span className="pill pill-accent">Settled</span>
          </div>
          <div className="call-takeaways">
            <div><dt>Confirmed</dt><dd>{money(savings.savedSoFar)} reduction, in writing</dd></div>
            <div><dt>Reference #</dt><dd className="mono-figure">{WRAP_UP_REF}</dd></div>
            <div><dt>New balance</dt><dd className="mono-figure">{money(savings.currentBalance)}</dd></div>
            <div><dt>Next action</dt><dd>None · case closed at your request</dd></div>
          </div>
        </div>
      )}
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
            <strong>Bay State Emergency Physicians</strong>
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

function DocumentsTab({ spec, cashedIn }: { spec: JobSpec; cashedIn: boolean }) {
  // Real files: the actual demo PDFs (data/demo_docs/, mirrored to
  // apps/web/public/demo-docs/) — this demo case's real uploaded documents,
  // not placeholders. Everything else (Supabase Storage for a real user's
  // own uploads) is still TODO(J)/TODO(Hamza) — bucket layout in
  // negotiator-intake-data-schema.md. Metadata fields (account #, claim #,
  // statement/due dates, line-item count) come straight from the JobSpec.
  const savings = facilitySavings(spec);
  const docs = [
    ...(cashedIn
      ? [{
          title: "Confirmation letter",
          type: "PDF",
          url: undefined,
          meta: [
            ["Reference #", WRAP_UP_REF],
            ["Confirmed reduction", money(savings.savedSoFar)],
            ["New balance", money(savings.currentBalance)],
          ],
        }]
      : []),
    {
      title: "Itemized bill",
      type: "PDF",
      url: "/demo-docs/mercy_general_bill.pdf",
      meta: [
        ["Account #", spec.bill.account_number],
        ["Statement date", spec.bill.statement_date ?? "–"],
        ["Due date", spec.bill.due_date ?? "–"],
        ["Line items", String(spec.bill.line_items.length)],
      ],
    },
    {
      title: "Explanation of Benefits (EOB)",
      type: "PDF",
      url: "/demo-docs/bcbs_eob.pdf",
      meta: [
        ["Claim #", spec.eob.claim_number ?? "–"],
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
          {doc.url ? (
            <a href={doc.url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ textDecoration: "none" }}>
              View {doc.type}
            </a>
          ) : (
            <button className="btn btn-secondary" disabled>Generating…</button>
          )}
        </div>
      ))}
      <div style={{ marginTop: 16 }}>
        <UploadCard
          title="Add another document"
          hint="Drag a PDF or photo: a follow-up letter, a second EOB, anything relevant to this bill"
        />
      </div>
      <p className="todo" style={{ marginTop: 16 }}>
        These are this demo case&apos;s real documents (data/demo_docs/). A real user&apos;s own uploads
        aren&apos;t wired to Supabase Storage yet (TODO Hamza/J).
      </p>
    </div>
  );
}
