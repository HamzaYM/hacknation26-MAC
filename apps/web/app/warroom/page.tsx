"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getCall } from "../../lib/api";
import { fetchCallEvents, subscribeToActiveCalls, subscribeToCall, subscribeToCallEvents } from "../../lib/realtime";
import Logo from "../../components/Logo";
import ReferenceChip from "../../components/ReferenceChip";
import ScenarioPicker from "../../components/ScenarioPicker";
import { LADDER_LABELS, QUESTION_LABELS, REQUIRED_QUESTIONS } from "../../lib/types";
import type { ActiveCall, Call, CallEvent } from "../../lib/types";

// This is a real live-call viewer, not a scripted before/after demo — it
// renders off the actual call_events/calls Realtime streams (lib/realtime.ts).
// Two modes: with ?call_id= it's the single-call deep view; without it, a
// multi-call overview of every call on the case (CallsOverview), one card per
// line. The writers are app/simulator.py (counterparty=agent, labeled
// "simulated persona · replay") and, when real dialing is on, the ElevenLabs
// webhook pipeline — either way this screen just renders what lands in the DB.

const KNOWN_LEVERS = [
  { id: "duplicate_charge", label: "Duplicate-charge dispute" },
  { id: "benchmark_anchor", label: "Price benchmark" },
  { id: "nsa", label: "No Surprises Act" },
  { id: "charity_care", label: "§501(r) charity care" },
];

// The two source documents this negotiation is built on, embedded in the right
// rail so the patient can watch the bill/EOB while the call runs. Served from
// apps/web/public/demo-docs/ (byte-identical to data/demo_docs/).
const CASE_DOCUMENTS = [
  {
    id: "bill",
    label: "Bill",
    url: "/demo-docs/mercy_general_bill.pdf",
    caption: "The itemized bill this negotiation is built on",
  },
  {
    id: "eob",
    label: "EOB",
    url: "/demo-docs/bcbs_eob.pdf",
    caption: "The insurer's EOB — what the plan says the patient owes",
  },
];

// The demo fixture's case UUID (apps/api/app/fixtures.py DEMO_CASE_ID). The
// overview has no case picker yet — the demo case is the only case that exists.
const DEMO_CASE_UUID = "00000000-0000-0000-0000-000000000001";

export default function WarRoomPage() {
  return (
    <Suspense fallback={null}>
      <WarRoom />
    </Suspense>
  );
}

// Reference/confirmation numbers the negotiator captured mid-call — from the
// structured tool payload (payload.reference_number) or parsed out of a tool
// result string ("…ref MRS-55217"). The patient reads these aloud, so we
// surface them as copyable chips. Requires an uppercase prefix + a dash so rep
// names ("Bob") never match.
function extractReferences(events: CallEvent[]): string[] {
  const refs = new Set<string>();
  for (const e of events) {
    const p = e.payload ?? {};
    const structured = p.reference_number;
    if (typeof structured === "string" && /\d/.test(structured)) refs.add(structured.trim());
    const result = typeof p.result === "string" ? p.result : "";
    const matches = result.match(/\b[A-Z]{2,}[A-Z0-9]*-[A-Z0-9-]{2,}\b/g);
    if (matches) matches.forEach((m) => refs.add(m));
  }
  return [...refs];
}

/** Append without duplicates (seed fetch + Realtime can overlap), id-ordered. */
function mergeEvents(prev: CallEvent[], incoming: CallEvent[]): CallEvent[] {
  const seen = new Set(prev.map((e) => e.id));
  const fresh = incoming.filter((e) => !seen.has(e.id));
  if (fresh.length === 0) return prev;
  return [...prev, ...fresh].sort((a, b) => a.id - b.id);
}

// Milestone feed icons — keyed off the same detection tokens the simulator
// and tools.py emit (disclose/honesty, lever_armed, quote, end_call_summary).
function milestoneIcon(e: CallEvent): { glyph: string; cls: string } {
  if (e.type === "quote") return { glyph: "$", cls: "quote" };
  const name = String(e.payload.name ?? "");
  if (name.includes("disclose") || name.includes("honesty")) return { glyph: "✓", cls: "disclosure" };
  if (name.includes("lever")) return { glyph: "⚡", cls: "lever" };
  if (name.includes("quote")) return { glyph: "$", cls: "quote" };
  if (name.includes("end_call") || name.includes("summary")) return { glyph: "⏹", cls: "outcome" };
  return { glyph: "·", cls: "" };
}

/** One compact card per call — live status, latest quote, current rung. */
function OverviewCard({ call }: { call: ActiveCall }) {
  const [events, setEvents] = useState<CallEvent[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetchCallEvents(call.id).then((list) => {
      if (!cancelled && list.length) setEvents((prev) => mergeEvents(prev, list));
    });
    const unsub = subscribeToCallEvents(call.id, (e) => setEvents((prev) => mergeEvents(prev, [e])));
    return () => {
      cancelled = true;
      unsub();
    };
  }, [call.id]);

  const quotes = events.filter((e) => e.type === "quote");
  const first = quotes[0]?.payload.amount as number | undefined;
  const latest = quotes.at(-1)?.payload.amount as number | undefined;
  const rung = events.filter((e) => e.type === "state_change").at(-1)?.payload.rung as string | undefined;

  // Coverage chip: only on cards whose current rung has required questions.
  const covRequired = rung ? REQUIRED_QUESTIONS[rung] ?? [] : [];
  const covAsked = covRequired.filter(
    (t) => events.some((e) => e.type === "question_covered" && e.payload.tag === t),
  ).length;

  return (
    <a className="wr-call-card" href={`/warroom?call_id=${call.id}`}>
      <div className="wr-call-head">
        <span className="wr-call-entity">{call.dossier?.target_entity ?? "Negotiation call"}</span>
        <span className={`wr-status-pill ${call.status}`}>{call.status === "live" ? "● live" : call.status}</span>
      </div>
      {call.counterparty === "agent" && <span className="wr-sim-badge">simulated persona · replay</span>}
      <div className="wr-call-quote">{latest != null ? `$${latest.toLocaleString()}` : "–"}</div>
      {first != null && latest != null && first > latest && (
        <div className="wr-call-delta">▼ ${(first - latest).toLocaleString()} this call</div>
      )}
      <div className="wr-call-rung">
        <span>{rung ? LADDER_LABELS[rung] ?? rung : "waiting for the first event"}</span>
        {covRequired.length > 0 && (
          <span className="wr-cov-chip mono-figure">{covAsked}/{covRequired.length} asked</span>
        )}
      </div>
    </a>
  );
}

/**
 * No ?call_id: every call for the case at once — the parallel-negotiation
 * view. Rendered off the calls + call_events Realtime streams, same as the
 * single-call view; nothing scripted on this side of the wire.
 */
// Keep the grid a live overview rather than an archive: every non-terminal
// call, plus calls that ended in the last 30 minutes (an outcome stays on
// screen through a demo run; yesterday's replays don't pile up).
const RECENT_ENDED_MS = 30 * 60 * 1000;
function isCurrent(call: ActiveCall): boolean {
  if (call.status !== "ended" && call.status !== "failed") return true;
  const endedAt = call.ended_at ? new Date(call.ended_at).getTime() : 0;
  return Date.now() - endedAt < RECENT_ENDED_MS;
}

function CallsOverview({ caseId }: { caseId: string }) {
  const router = useRouter();
  const [allCalls, setAllCalls] = useState<ActiveCall[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const calls = allCalls.filter(isCurrent);
  const anyEnded = allCalls.some((c) => c.status === "ended" || c.status === "failed");

  useEffect(() => {
    setAllCalls([]);
    return subscribeToActiveCalls(caseId, setAllCalls);
  }, [caseId]);

  function onScenarioLoaded(newCaseId: string) {
    setPickerOpen(false);
    router.push(`/warroom?case_id=${newCaseId}`);
  }

  const scenarioStrip = (
    <div className="wr-panel" style={{ marginBottom: 20 }}>
      <button
        onClick={() => setPickerOpen((o) => !o)}
        style={{ background: "none", border: "none", padding: 0, cursor: "pointer", width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center" }}
      >
        <h2 style={{ marginBottom: 0 }}>Scenarios{caseId !== DEMO_CASE_UUID && <span style={{ marginLeft: 8 }} className="wr-sim-badge">case: {caseId.slice(0, 8)}</span>}</h2>
        <span style={{ color: "rgba(245,241,236,0.5)", fontSize: 12 }}>{pickerOpen ? "▾ hide" : "▸ switch scenario"}</span>
      </button>
      {pickerOpen && (
        <div style={{ marginTop: 16 }}>
          <ScenarioPicker onLoaded={onScenarioLoaded} />
        </div>
      )}
    </div>
  );

  if (calls.length === 0) {
    return (
      <>
        {scenarioStrip}
        <div className="wr-idle">
          <div className="wr-idle-icon">☎</div>
          <h2>Waiting for the calls</h2>
          <p>
            This overview renders directly off the <code>calls</code> and <code>call_events</code> Realtime
            streams. Nothing here is scripted. Launch from a bill&apos;s Plan tab (&quot;Start the
            calls&quot;) and every line appears here as it dials. Or open{" "}
            <code>?call_id=&lt;id&gt;</code> to watch a single one — or pick a different scenario above.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      {scenarioStrip}
      {anyEnded && (
        <div className="wr-report-cta" role="status">
          <div className="wr-report-cta-text">
            <strong>Some calls have wrapped up.</strong> See every outcome, reference number, and next step in one place.
          </div>
          <a href="/report" className="btn btn-primary" style={{ textDecoration: "none", whiteSpace: "nowrap" }}>
            See the report →
          </a>
        </div>
      )}
      <div className="wr-overview-grid">
        {calls.map((c) => (
          <OverviewCard key={c.id} call={c} />
        ))}
      </div>
      <p className="wr-overview-note">
        One negotiator, {calls.length} lines in parallel. Click a card for the full transcript and
        event log. Calls labeled <span className="wr-sim-badge">simulated persona · replay</span> run
        against a scripted counterparty, not a live phone line.
      </p>
    </>
  );
}

function HonestyAudit({ toolCalls }: { toolCalls: CallEvent[] }) {
  const audit = toolCalls.find((e) => String(e.payload.name ?? "").includes("honesty_audit"));
  if (!audit) return null;
  const passed = String(audit.payload.result ?? "").includes("passed");
  return (
    <>
      <h2>Honesty audit</h2>
      <div className="wr-honesty">
        <span className="count">{passed ? "✓" : "…"}</span>
        {String(audit.payload.result ?? "pending")}
      </div>
    </>
  );
}

// Covered/flagged tags derived from the live event stream. Coverage is global
// (the engine's questions_covered is not per-rung), so a covered tag counts on
// whichever rung requires it; coverage_gap flags are scoped to their own rung.
function coverageState(events: CallEvent[], rung: string | undefined) {
  const covered = new Set<string>();
  const flagged = new Set<string>();
  for (const e of events) {
    if (e.type === "question_covered" && typeof e.payload.tag === "string") {
      covered.add(e.payload.tag);
    } else if (e.type === "coverage_gap" && e.payload.rung === rung && Array.isArray(e.payload.missing)) {
      (e.payload.missing as unknown[]).forEach((m) => flagged.add(String(m)));
    }
  }
  return { covered, flagged };
}

/**
 * The engine FORCES the agent to ask each rung's required questions before the
 * call can move on. This renders the current rung's list and flips each row
 * amber(pending) → green(covered) off question_covered events; a coverage_gap
 * turns an un-asked row coral (the agent tried to advance while still missing it).
 */
function CoveragePanel({ events, rung }: { events: CallEvent[]; rung?: string }) {
  const required = rung ? REQUIRED_QUESTIONS[rung] ?? [] : [];
  const { covered, flagged } = coverageState(events, rung);
  const askedCount = required.filter((t) => covered.has(t)).length;

  return (
    <div className="wr-panel">
      <div className="wr-cov-head">
        <h2 style={{ marginBottom: 0 }}>Coverage</h2>
        {required.length > 0 && (
          <span className="wr-cov-count mono-figure">{askedCount}/{required.length} asked</span>
        )}
      </div>
      {rung && <div className="wr-cov-rung">{LADDER_LABELS[rung] ?? rung}</div>}
      {!rung ? (
        <p className="wr-cov-empty">Waiting for the first rung…</p>
      ) : required.length === 0 ? (
        <p className="wr-cov-empty">No required questions on this rung.</p>
      ) : (
        <>
          <div className="wr-cov-list">
            {required.map((tag) => {
              const isCovered = covered.has(tag);
              const isFlagged = !isCovered && flagged.has(tag);
              const state = isCovered ? "covered" : isFlagged ? "flagged" : "pending";
              return (
                <div className="wr-cov-row" key={tag}>
                  <span className={`wr-cov-dot ${state}`} aria-hidden>{isCovered ? "✓" : isFlagged ? "!" : ""}</span>
                  <span className="wr-cov-tag mono-figure">{QUESTION_LABELS[tag] ?? tag.replace(/_/g, " ")}</span>
                </div>
              );
            })}
          </div>
          <p className="wr-cov-caption">The engine will not let the call move on until these are asked.</p>
        </>
      )}
    </div>
  );
}

// Bill + EOB embedded so the patient can watch the source documents while the
// call runs. PDFs render white; a thin border + rounded corners keeps them calm
// against the dark War Room. Borrows the intake iframe-preview pattern — and,
// like that pattern, clicking the small preview opens it full-screen so the
// patient can actually read the line items (a 360px iframe can't be read).
function DocumentsPanel() {
  const [active, setActive] = useState(CASE_DOCUMENTS[0]);
  const [lightbox, setLightbox] = useState<(typeof CASE_DOCUMENTS)[number] | null>(null);

  // Escape closes the lightbox (matches the click-outside close below).
  useEffect(() => {
    if (!lightbox) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightbox(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightbox]);

  return (
    <div className="wr-panel wr-docs">
      <div className="wr-docs-head">
        <h2 style={{ marginBottom: 0 }}>Documents</h2>
        <button
          type="button"
          className="wr-docs-expand"
          onClick={() => setLightbox(active)}
          aria-label={`Open ${active.label} full screen`}
        >
          ⤢ Enlarge
        </button>
      </div>
      <div className="wr-docs-tabs">
        {CASE_DOCUMENTS.map((d) => (
          <button
            key={d.id}
            className={`wr-docs-tab ${active.id === d.id ? "active" : ""}`}
            onClick={() => setActive(d)}
          >
            {d.label}
          </button>
        ))}
      </div>
      <p className="wr-docs-caption mono-figure">{active.caption}</p>
      {/* The iframe swallows pointer events, so the wrapper carries the click and
          the iframe is pointer-inert — clicking anywhere on the preview enlarges. */}
      <div
        className="wr-doc-preview"
        role="button"
        tabIndex={0}
        aria-label={`Enlarge ${active.label}`}
        onClick={() => setLightbox(active)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setLightbox(active);
          }
        }}
      >
        <iframe className="wr-doc-frame" src={active.url} title={active.label} />
        <span className="wr-doc-hint">⤢ Click to enlarge</span>
      </div>

      {lightbox && (
        <div className="wr-doc-overlay" onClick={() => setLightbox(null)}>
          <div className="wr-doc-lightbox" onClick={(e) => e.stopPropagation()}>
            <div className="wr-doc-lightbox-head">
              <span className="wr-doc-lightbox-title">
                {lightbox.label} <span className="mono-figure">· {lightbox.caption}</span>
              </span>
              <button
                type="button"
                className="wr-doc-lightbox-close"
                onClick={() => setLightbox(null)}
                aria-label="Close document"
              >
                ✕
              </button>
            </div>
            <iframe className="wr-doc-lightbox-frame" src={lightbox.url} title={lightbox.label} />
          </div>
        </div>
      )}
    </div>
  );
}

function WarRoom() {
  const searchParams = useSearchParams();
  const callId = searchParams.get("call_id");
  // Scenario picker (decision #11): ?case_id= drives which case's calls this
  // board shows; absent it, the Maya demo case (unchanged default behavior).
  const caseId = searchParams.get("case_id") ?? DEMO_CASE_UUID;
  const [call, setCall] = useState<Call | null>(null);
  const [events, setEvents] = useState<CallEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!callId) return;
    let cancelled = false;

    getCall(callId).then((c) => !cancelled && setCall(c)).catch(() => {});

    // Seed with what's already persisted, so a card clicked mid-call (or an
    // ended call) shows its history — then stay live off the same stream.
    fetchCallEvents(callId).then((list) => {
      if (!cancelled && list.length) {
        setConnected(true);
        setEvents((prev) => mergeEvents(prev, list));
      }
    });

    const unsubCall = subscribeToCall(callId, (c) => setCall(c));
    const unsubEvents = subscribeToCallEvents(callId, (e) => {
      setConnected(true);
      setEvents((prev) => mergeEvents(prev, [e]));
    });

    return () => {
      cancelled = true;
      unsubCall();
      unsubEvents();
    };
  }, [callId]);

  const quotes = events.filter((e) => e.type === "quote");
  const latestQuote = quotes.at(-1)?.payload.amount as number | undefined;
  const firstQuote = quotes[0]?.payload.amount as number | undefined;

  // Price-move emphasis: when a new quote LOWERS the amount, flash the ticker
  // and float a −$X chip. The seed fetch lands as one batch (prev is null on
  // the first quote seen), so only live downward moves fire it.
  const prevQuoteRef = useRef<number | null>(null);
  const [drop, setDrop] = useState<{ amount: number; key: number } | null>(null);
  useEffect(() => {
    if (latestQuote == null) return;
    const prev = prevQuoteRef.current;
    prevQuoteRef.current = latestQuote;
    if (prev != null && latestQuote < prev) setDrop({ amount: prev - latestQuote, key: Date.now() });
  }, [latestQuote]);
  useEffect(() => {
    if (!drop) return;
    // Timeout (not animationend) so the chip also clears under prefers-reduced-motion.
    const t = setTimeout(() => setDrop(null), 1800);
    return () => clearTimeout(t);
  }, [drop]);
  const transcript = events.filter((e) => e.type === "transcript");
  const toolCalls = events.filter((e) => e.type === "tool_call");
  const milestones = events.filter((e) => e.type === "tool_call" || e.type === "quote");
  const stateChanges = events.filter((e) => e.type === "state_change");
  const latestRung = stateChanges.at(-1)?.payload as { rung?: string; rung_index?: number } | undefined;
  const disclosed = toolCalls.some((e) => String(e.payload.name ?? "").includes("disclose"));
  const references = extractReferences(events);
  const ended = call?.status === "ended" || call?.status === "failed";
  const isLive = call?.status === "live" || call?.status === "ringing";

  return (
    <div className="warroom-shell">
      <div className="topbar-wr">
        <Logo />
        <span style={{ fontSize: 13, color: "rgba(245,241,236,0.5)" }}>
          {connected ? "● connected" : callId ? "connecting…" : "no call selected"}
        </span>
      </div>
      <div className="warroom-meta">
        {call ? (
          <>
            {`Call ${String(call.id ?? callId).slice(0, 8)} · status: ${call.status}`}
            {call.counterparty === "agent" && (
              <span className="wr-sim-badge" style={{ marginLeft: 10 }}>simulated persona · replay</span>
            )}
            <a
              href={caseId !== DEMO_CASE_UUID ? `/warroom?case_id=${caseId}` : "/warroom"}
              style={{ marginLeft: 14, fontSize: 12, color: "rgba(245,241,236,0.5)" }}
            >
              ← all calls
            </a>
          </>
        ) : callId ? `Call ${callId.slice(0, 8)}` : "War Room · every line for this case, live"}
      </div>

      {ended && (
        <div className="wr-report-cta" role="status">
          <div className="wr-report-cta-text">
            <strong>This call wrapped up.</strong> See how it landed — and what happens next — in the full report.
          </div>
          <a href="/report" className="btn btn-primary" style={{ textDecoration: "none", whiteSpace: "nowrap" }}>
            See the report →
          </a>
        </div>
      )}

      <div className="warroom-layout">
        <div>
          {!callId ? (
            <CallsOverview caseId={caseId} />
          ) : events.length === 0 ? (
            <div className="wr-idle">
              <div className="wr-idle-icon pulse">●</div>
              <h2>{isLive ? "Connected. The negotiator is on the line." : "Connected, waiting for the call to start"}</h2>
              <p>
                {isLive ? (
                  "Moves appear here the moment the engine drives one — required questions, quotes, and reference numbers land live."
                ) : (
                  <>No events yet for call <span className="mono-figure">{callId}</span>. This will populate live the moment the agent dials.</>
                )}
              </p>
            </div>
          ) : (
            <div className="warroom-grid">
              {/* human panel */}
              <div className="wr-panel">
                <h2>Live</h2>

                <div style={{ textAlign: "center", fontSize: 13, color: "rgba(245,241,236,0.5)" }}>
                  Balance · negotiating
                </div>
                <div className="wr-ticker-wrap">
                  {/* key remounts restart the CSS animations on every drop;
                      ticker and chip keys must differ or React reconciliation
                      cross-matches the two divs and strands stale text. */}
                  <div className={`wr-ticker${drop ? " wr-ticker-drop" : ""}`} key={`ticker-${drop?.key ?? "idle"}`}>
                    {latestQuote != null ? `$${latestQuote.toLocaleString()}` : "–"}
                  </div>
                  {drop && (
                    <div className="wr-drop-chip mono-figure" key={`chip-${drop.key}`}>
                      −${drop.amount.toLocaleString()}
                    </div>
                  )}
                </div>
                {firstQuote != null && latestQuote != null && firstQuote !== latestQuote && (
                  <div className="wr-ticker-delta">
                    {latestQuote < firstQuote ? "▼" : "▲"} ${Math.abs(firstQuote - latestQuote).toLocaleString()} moved this call
                  </div>
                )}

                <h2 style={{ marginTop: 24 }}>Transcript</h2>
                <div className="wr-transcript">
                  {transcript.length === 0 && (
                    <p style={{ color: "rgba(245,241,236,0.4)", fontSize: 13 }}>
                      {isLive ? "Transcript lands here after the call." : "No transcript lines yet."}
                    </p>
                  )}
                  {transcript.map((e) => (
                    <div className="wr-line" key={e.id}>
                      <span className="speaker">{String(e.payload.speaker ?? "?")}</span>
                      {String(e.payload.text ?? "")}
                    </div>
                  ))}
                </div>

                {disclosed && (
                  <div style={{ marginTop: 20, fontSize: 12, color: "rgba(245,241,236,0.5)" }}>
                    AI advocate has disclosed · call recorded
                  </div>
                )}
              </div>

              {/* proof panel */}
              <div className="wr-panel">
                <HonestyAudit toolCalls={toolCalls} />

                {references.length > 0 && (
                  <>
                    <h2>Reference numbers</h2>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
                      {references.map((r) => (
                        <ReferenceChip key={r} label="Ref" value={r} tone="dark" />
                      ))}
                    </div>
                  </>
                )}

                <h2>Current step</h2>
                <div style={{ fontSize: 15, marginBottom: 20 }}>
                  {latestRung?.rung ? LADDER_LABELS[latestRung.rung] ?? latestRung.rung : "–"}
                </div>

                <h2>Milestone feed <span style={{ color: "var(--accent)" }}>live</span></h2>
                <div className="wr-event-log">
                  {milestones.length === 0 && <p style={{ color: "rgba(245,241,236,0.4)" }}>No milestones yet.</p>}
                  {milestones.map((e) => {
                    const icon = milestoneIcon(e);
                    return (
                      <div key={e.id}>
                        <div>
                          <span className={`wr-mile-icon ${icon.cls}`}>{icon.glyph}</span>
                          <span className="ts">{new Date(e.ts).toLocaleTimeString()}</span>
                          <span className="call-fn">{e.type === "quote" ? "quote" : String(e.payload.name ?? "tool_call")}</span>
                        </div>
                        {e.type === "quote" ? (
                          <div className="ret">→ ${Number(e.payload.amount ?? 0).toLocaleString()}</div>
                        ) : (
                          typeof e.payload.result === "string" && <div className="ret">→ {e.payload.result}</div>
                        )}
                      </div>
                    );
                  })}
                </div>

                <h2 style={{ marginTop: 20 }}>Levers</h2>
                <div>
                  {KNOWN_LEVERS.map((lever) => {
                    const armedEvent = toolCalls.find((e) => String(e.payload.name ?? "").includes(lever.id));
                    return (
                      <div className="wr-lever-row" key={lever.id}>
                        <div>{lever.label}</div>
                        <span className={`wr-lever-state ${armedEvent ? "armed" : "dormant"}`}>
                          {armedEvent ? "ARMED" : "DORMANT"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="wr-rail">
          {callId && <CoveragePanel events={events} rung={latestRung?.rung} />}
          <DocumentsPanel />
        </div>
      </div>
    </div>
  );
}
