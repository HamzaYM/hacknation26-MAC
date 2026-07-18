"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getCall } from "../../lib/api";
import { subscribeToCall, subscribeToCallEvents } from "../../lib/realtime";
import Logo from "../../components/Logo";
import type { Call, CallEvent } from "../../lib/types";

// This is a real live-call viewer, not a scripted before/after demo — it
// renders off the actual call_events/calls Realtime streams (lib/realtime.ts).
// There is currently nothing writing to those tables yet (tools.py's
// log_quote/log_event/end_call_summary are still stubs — see Hamza's TODOs),
// so right now this mostly shows the "waiting for a call" state below. That's
// intentional: once a real ElevenLabs call is launched and the backend
// writes events, this screen updates live with no further frontend changes.

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

export default function WarRoomPage() {
  return (
    <Suspense fallback={null}>
      <WarRoom />
    </Suspense>
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
  const callId = useSearchParams().get("call_id");
  const [call, setCall] = useState<Call | null>(null);
  const [events, setEvents] = useState<CallEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!callId) return;
    let cancelled = false;

    getCall(callId).then((c) => !cancelled && setCall(c)).catch(() => {});

    const unsubCall = subscribeToCall(callId, (c) => setCall(c));
    const unsubEvents = subscribeToCallEvents(callId, (e) => {
      setConnected(true);
      setEvents((prev) => [...prev, e]);
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
  const transcript = events.filter((e) => e.type === "transcript");
  const toolCalls = events.filter((e) => e.type === "tool_call");
  const stateChanges = events.filter((e) => e.type === "state_change");
  const latestRung = stateChanges.at(-1)?.payload as { rung?: string; rung_index?: number } | undefined;
  const disclosed = toolCalls.some((e) => String(e.payload.name ?? "").includes("disclose"));

  return (
    <div className="warroom-shell">
      <div className="topbar-wr">
        <Logo />
        <span style={{ fontSize: 13, color: "rgba(245,241,236,0.5)" }}>
          {connected ? "● connected" : callId ? "connecting…" : "no call selected"}
        </span>
      </div>
      <div className="warroom-meta">
        {call ? `Call ${call.id.slice(0, 8)} · ${call.counterparty} · status: ${call.status}` : callId ? `Call ${callId.slice(0, 8)}` : "War Room"}
      </div>

      <div className="warroom-layout">
        <div>
          {!callId ? (
            <div className="wr-idle">
              <div className="wr-idle-icon">☎</div>
              <h2>Waiting for a live call</h2>
              <p>
                This screen renders directly off the <code>call_events</code> Realtime stream — nothing
                here is scripted. Launch a call from a bill&apos;s Plan tab (once call-launching is
                wired) or open this page with <code>?call_id=&lt;id&gt;</code> to watch a specific one.
              </p>
            </div>
          ) : events.length === 0 ? (
            <div className="wr-idle">
              <div className="wr-idle-icon pulse">●</div>
              <h2>Connected — waiting for the call to start talking</h2>
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
                <div className="wr-ticker">{latestQuote != null ? `$${latestQuote.toLocaleString()}` : "—"}</div>
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

                <h2>Current step</h2>
                <div style={{ fontSize: 15, marginBottom: 20 }}>
                  {latestRung?.rung ?? "—"}
                </div>

                <h2>Event log · tool calls <span style={{ color: "var(--accent)" }}>live</span></h2>
                <div className="wr-event-log">
                  {toolCalls.length === 0 && <p style={{ color: "rgba(245,241,236,0.4)" }}>No tool calls yet.</p>}
                  {toolCalls.map((e) => (
                    <div key={e.id}>
                      <div>
                        <span className="ts">{new Date(e.ts).toLocaleTimeString()}</span>
                        <span className="call-fn">{String(e.payload.name ?? "tool_call")}</span>
                      </div>
                      {typeof e.payload.result === "string" && <div className="ret">→ {e.payload.result}</div>}
                    </div>
                  ))}
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
