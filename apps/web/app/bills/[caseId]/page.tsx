"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getBenchmarkReport, getCase, getReport, launchCalls } from "../../../lib/api";
import { subscribeToCallsForCase } from "../../../lib/realtime";
import { facilitySavings, money } from "../../../lib/savings";
import { procedureLabel } from "../../../lib/procedures";
import UploadCard from "../../../components/UploadCard";
import ActionItemCard from "../../../components/ActionItemCard";
import MultiplesTable from "../../../components/MultiplesTable";
import { itemsForEntity } from "../../../lib/actionItems";
import { FLAG_LABELS, LADDER_LABELS, OUTCOME_LABELS, PROVIDER_LADDER } from "../../../lib/types";
import type { JobSpec, DerivedFlag, Call, BenchmarkReport, CaseReport } from "../../../lib/types";

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
  // Bill-scoped completion state, mirrored to localStorage per case so checks
  // survive reload. Separate from the aggregate /action-items page's own store;
  // a shared server-side source of truth for both views is still to come.
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

  // Restore this case's completed action items from localStorage (reset when
  // switching cases so completions never leak across bills).
  useEffect(() => {
    if (!caseId) return;
    try {
      const raw = window.localStorage.getItem(`haggl.actionItems.${caseId}`);
      setCompletedActionIds(raw ? new Set(JSON.parse(raw) as string[]) : new Set());
    } catch {
      setCompletedActionIds(new Set());
    }
  }, [caseId]);

  function completeAction(id: string) {
    setCompletedActionIds((prev) => {
      const next = new Set(prev).add(id);
      try {
        window.localStorage.setItem(`haggl.actionItems.${caseId}`, JSON.stringify([...next]));
      } catch {}
      return next;
    });
  }

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
        We could not load this case right now. Refresh in a moment, or go back to{" "}
        <a href="/bills">your bills</a>.
      </p>
    );
  }
  if (!spec) return <p className="todo">Loading case…</p>;

  const savings = facilitySavings(spec);
  const barTotal = savings.percentSavedSoFar + savings.percentProjectedHigh;
  const achievedWidth = barTotal > 0 ? (savings.percentSavedSoFar / barTotal) * 100 : 0;
  const projectedWidth = barTotal > 0 ? (savings.percentProjectedHigh / barTotal) * 100 : 0;

  return (
    <div data-testid="case-file">
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
              <ActionsTab items={pendingActions} onComplete={completeAction} />
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
        {eobMismatch ? (
          <>there&apos;s a billing error inflating this bill by <strong>{money(eobMismatch.dollar_impact)}</strong></>
        ) : (
          <>we found <strong>{money(totalFlagged)}</strong> in charges worth challenging on this bill</>
        )}
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
    <div className="finding-card" data-testid="finding-card" data-flag-type={flag.type}>
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
    } catch (err) {
      setLaunching(false);
      // A fetch network failure rejects with a TypeError (nothing reached the
      // server); anything else means we got a response back and it went wrong.
      const networkFailure = err instanceof TypeError;
      setLaunchError(
        networkFailure
          ? "We could not reach Haggl to start the calls. Check your connection and try again in a moment."
          : "We could not start the calls just now. Nothing was dialed. Refresh in a moment and try again."
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
                    Agent is citing the Medicare rate and {spec.bill.facility_name}&apos;s own posted cash price
                    for these codes to argue the balance down.
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
  // Real call history, read from GET /cases/{id}/report — the outcomes the
  // calls actually produced. Empty (honest empty state) until a call wraps up.
  const savings = facilitySavings(spec);
  const [report, setReport] = useState<CaseReport | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    getReport(spec.case_id)
      .then((r) => { if (active) setReport(r); })
      .catch(() => {})
      .finally(() => { if (active) setLoaded(true); });
    return () => { active = false; };
  }, [spec.case_id]);

  const outcomes = report?.outcomes ?? [];

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
      {outcomes.map((o, i) => {
        const removed =
          o.original_amount != null && o.final_amount != null ? o.original_amount - o.final_amount : null;
        const settled = o.outcome_type !== "callback" && o.outcome_type !== "documented_decline";
        const resolved =
          o.resolved_at && !Number.isNaN(new Date(o.resolved_at).getTime())
            ? new Date(o.resolved_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
            : null;
        const meta = [resolved, o.rep_name ? `rep ${o.rep_name}` : null].filter(Boolean).join(" · ");
        const hasTakeaways = o.winning_lever || o.reference_number || (removed != null && removed > 0) || o.next_action;
        return (
          <div className="call-row" key={o.call_id ?? i}>
            <div className="call-row-head">
              <div>
                <strong>{o.entity ?? spec.bill.facility_name}</strong>
                {meta && <div className="call-row-meta">{meta}</div>}
              </div>
              <span className={`pill ${settled ? "pill-accent" : "pill-muted"}`}>
                {o.outcome_type ? OUTCOME_LABELS[o.outcome_type] : "Outcome"}
              </span>
            </div>
            {hasTakeaways && (
              <div className="call-takeaways">
                {o.winning_lever && <div><dt>Winning lever</dt><dd>{o.winning_lever}</dd></div>}
                {o.reference_number && <div><dt>Reference #</dt><dd className="mono-figure">{o.reference_number}</dd></div>}
                {removed != null && removed > 0 && (
                  <div><dt>Amount removed</dt><dd className="mono-figure" style={{ color: "var(--accent)" }}>−{money(removed)}</dd></div>
                )}
                {o.next_action && <div><dt>Next action</dt><dd>{o.next_action}</dd></div>}
              </div>
            )}
          </div>
        );
      })}
      {loaded && !cashedIn && outcomes.length === 0 && (
        <p className="todo" style={{ borderColor: "var(--border)", background: "var(--bg-surface-muted)", color: "var(--text-secondary)" }}>
          No calls have wrapped up on this bill yet. When Haggl finishes a call, the outcome and its reference number show up here.
        </p>
      )}
    </div>
  );
}

function DocumentsTab({ spec, cashedIn }: { spec: JobSpec; cashedIn: boolean }) {
  // Real files: the actual demo PDFs (data/demo_docs/, mirrored to
  // apps/web/public/demo-docs/). Metadata fields (account #, claim #,
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
          {doc.url && (
            <a href={doc.url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ textDecoration: "none" }}>
              View {doc.type}
            </a>
          )}
        </div>
      ))}
      <div style={{ marginTop: 16 }}>
        <UploadCard
          title="Add another document"
          hint="Drag a PDF or photo: a follow-up letter, a second EOB, anything relevant to this bill"
        />
      </div>
    </div>
  );
}
