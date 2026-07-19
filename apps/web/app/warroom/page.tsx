"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getCall } from "../../lib/api";
import { fetchCallEvents, subscribeToActiveCalls, subscribeToCall, subscribeToCallEvents } from "../../lib/realtime";
import Logo from "../../components/Logo";
import ReferenceChip from "../../components/ReferenceChip";
import ScenarioPicker from "../../components/ScenarioPicker";
import { LADDER_LABELS } from "../../lib/types";
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

// The advocate roster — three ElevenLabs personas the negotiator can be
// voiced as. Not counterparty personas (those live in prompts/personas/);
// this is the side placing the call. Static reference, not tied to live
// call data — which persona a real call used isn't persisted anywhere yet.
const ADVOCATE_PERSONAS = [
  {
    name: "Alex",
    style: "Warm & Persistent",
    voice: "Angela",
    why: "Disarms front-line reps first — positive politeness and mild hardship framing extract more than a purely rational pitch from a low-power position.",
    pickedFor: "Opening calls, front-line reps, rapport → escalation",
  },
  {
    name: "Morgan",
    style: "Calm & Analytical",
    voice: "Archer (tuned lower)",
    why: "Leads with citations, not emotion — competence reads stronger than warmth once a call gets high-severity or a supervisor wants numbers, not a story.",
    pickedFor: "Supervisors, policy-citers, benchmark-anchor moments",
  },
  {
    name: "Riley",
    style: "Direct & Assertive",
    voice: "search: professional + fast",
    why: "Zero rapport-spend — warmth reads as an opening to be dismissed on a collections call. Firm, never angry (anger backfires for a disclosed AI).",
    pickedFor: "Collections, settlement pushes, post-stonewall callbacks",
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
      <div className="wr-call-rung">{rung ? LADDER_LABELS[rung] ?? rung : "waiting for the first event"}</div>
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
        event log. Cards marked <span className="wr-sim-badge">simulated persona · replay</span> are
        negotiations against a scripted counterpart persona, not a human on a phone line. The{" "}
        <code>calls.counterparty</code> field is the source of that label.
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

function AdvocateRoster() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`wr-panel wr-roster ${collapsed ? "collapsed" : ""}`}>
      <button className="wr-roster-toggle" onClick={() => setCollapsed((c) => !c)}>
        <h2 style={{ marginBottom: 0 }}>Advocates</h2>
        <span className="wr-roster-chevron">{collapsed ? "▸" : "▾"}</span>
      </button>
      {!collapsed && (
        <>
          <p style={{ fontSize: 12, color: "rgba(245,241,236,0.5)", margin: "12px 0 16px", lineHeight: 1.5 }}>
            Same negotiator, three personas. Honesty and disclosure rules are structural — identical
            for all three, not persona-dependent.
          </p>
          {ADVOCATE_PERSONAS.map((p) => (
            <div className="wr-persona-card" key={p.name}>
              <div className="wr-persona-head">
                <strong>{p.name}</strong>
                <span className="wr-persona-style">{p.style}</span>
              </div>
              <div className="wr-persona-voice mono-figure">{p.voice}</div>
              <p className="wr-persona-why">{p.why}</p>
              <div className="wr-persona-for">Picked for: {p.pickedFor}</div>
            </div>
          ))}
        </>
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
              <h2>Connected, waiting for the call to start talking</h2>
              <p>No events yet for call <span className="mono-figure">{callId}</span>. This will populate live the moment the agent dials.</p>
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
                  {transcript.length === 0 && <p style={{ color: "rgba(245,241,236,0.4)", fontSize: 13 }}>No transcript lines yet.</p>}
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

        <AdvocateRoster />
      </div>
    </div>
  );
}
