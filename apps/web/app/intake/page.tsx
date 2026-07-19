"use client";

import { useEffect, useRef, useState } from "react";
import Script from "next/script";
import UploadCard from "../../components/UploadCard";
import ParsedDocPreview from "../../components/ParsedDocPreview";
import { getDemoCase, parseDocument, saveFinancialProfile } from "../../lib/api";
import type { FinancialProfileInput, ParseDocumentResponse } from "../../lib/api";
import { money } from "../../lib/savings";

// ElevenLabs conversation widget — standard custom element, script loaded below.
declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "elevenlabs-convai": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        "agent-id": string;
      };
    }
  }
}

const INTAKE_AGENT_ID = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID_INTAKE;

type DocKind = "bill" | "eob";

type SlotState =
  | { status: "idle" }
  | { status: "parsing"; fileName: string }
  | { status: "error"; fileName: string; file: File }
  | { status: "done"; fileName: string; result: ParseDocumentResponse };

const SLOT_COPY: Record<DocKind, { section: string; title: string; hint: string }> = {
  bill: {
    section: "Your hospital bill",
    title: "Upload the itemized bill",
    hint: "Drag a PDF or photo of the hospital bill here",
  },
  eob: {
    section: "Your insurance EOB · optional, unlocks cross-checks",
    title: "Upload the Explanation of Benefits",
    hint: "Drag the EOB from your insurer here. It lets us check what the hospital billed",
  },
};

export default function Intake() {
  const [slots, setSlots] = useState<Record<DocKind, SlotState>>({
    bill: { status: "idle" },
    eob: { status: "idle" },
  });
  // The case the interview's answers attach to. Resolved from the demo case so
  // the manual card / webhook capture and the /confirm screen share one spec.
  const [caseId, setCaseId] = useState<string | null>(null);
  useEffect(() => {
    getDemoCase()
      .then((s) => setCaseId(s.case_id))
      .catch(() => setCaseId(null));
  }, []);

  function setSlot(kind: DocKind, state: SlotState) {
    setSlots((prev) => ({ ...prev, [kind]: state }));
  }

  async function parse(kind: DocKind, file: File) {
    setSlot(kind, { status: "parsing", fileName: file.name });
    try {
      const result = await parseDocument(file, kind);
      setSlot(kind, { status: "done", fileName: file.name, result });
    } catch {
      setSlot(kind, { status: "error", fileName: file.name, file });
    }
  }

  const billDone = slots.bill.status === "done";

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>Intake</span>
        <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>takes ~5 min</span>
      </div>
      <h1 style={{ fontSize: 30, marginBottom: 8 }}>Add your documents</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: 8 }}>
        We read the bill and EOB line by line, check them against your case records, and flag
        anything worth arguing. Then a short voice interview covers what documents can&apos;t tell us.
      </p>
      <p style={{ fontSize: 13, color: "var(--text-tertiary)", marginBottom: 24 }}>
        🔒 Encrypted in transit and at rest. Used only to negotiate this bill.
      </p>

      {(["bill", "eob"] as DocKind[]).map((kind) => (
        <section key={kind} style={{ marginBottom: 24 }}>
          <h3
            style={{
              fontSize: 13,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--text-tertiary)",
              marginBottom: 12,
            }}
          >
            {SLOT_COPY[kind].section}
          </h3>
          <DocSlot
            kind={kind}
            state={slots[kind]}
            onFile={(file) => parse(kind, file)}
            onReset={() => setSlot(kind, { status: "idle" })}
          />
        </section>
      ))}

      <section style={{ marginBottom: 24 }}>
        <h3
          style={{
            fontSize: 13,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--text-tertiary)",
            marginBottom: 12,
          }}
        >
          Voice interview
        </h3>
        <VoiceInterviewCard caseId={caseId} />
      </section>

      {billDone && (
        <a href="/bills" className="btn btn-primary" style={{ textDecoration: "none" }}>
          Continue to your bills →
        </a>
      )}
    </div>
  );
}

function DocSlot({
  kind,
  state,
  onFile,
  onReset,
}: {
  kind: DocKind;
  state: SlotState;
  onFile: (file: File) => void;
  onReset: () => void;
}) {
  if (state.status === "idle") {
    return <UploadCard title={SLOT_COPY[kind].title} hint={SLOT_COPY[kind].hint} onSelect={onFile} />;
  }

  if (state.status === "parsing") {
    return (
      <div className="document-card" style={{ marginBottom: 0 }}>
        <div className="document-icon">📄</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600 }}>{state.fileName}</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "var(--accent)",
                marginRight: 8,
                animation: "haggl-pulse 1.6s ease-in-out infinite",
              }}
            />
            Reading the document: extracting line items and checking them against your case records…
          </div>
        </div>
        <span className="pill pill-muted">Parsing</span>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div>
        <p className="todo" style={{ marginBottom: 8 }}>
          We could not read <strong>{state.fileName}</strong> right now. Your file is still here, nothing was lost. Refresh in a moment and try again.
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-secondary" onClick={() => onFile(state.file)}>
            Try again
          </button>
          <button
            type="button"
            onClick={onReset}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-tertiary)",
              fontSize: 13,
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            Choose a different file
          </button>
        </div>
      </div>
    );
  }

  return <ParsedDocPreview kind={kind} fileName={state.fileName} result={state.result} onReset={onReset} />;
}

// Best-effort read of "what the widget heard" off a convai end/disconnect event.
// The embed widget's event payload isn't a guaranteed contract, so this only
// pre-fills when a dollar amount is actually accessible; otherwise the card
// opens with empty inputs and the server-side webhook remains the reliable path.
function extractHeard(e: Event): FinancialProfileInput | null {
  const detail = (e as CustomEvent).detail;
  const text =
    typeof detail === "string" ? detail : detail && typeof detail === "object" ? JSON.stringify(detail) : "";
  const m = text.match(/put down[^$0-9]*\$?\s?([0-9][0-9,]*)/i) ?? text.match(/\$\s?([0-9][0-9,]*)/);
  if (!m) return null;
  const n = parseFloat(m[1].replace(/,/g, ""));
  return Number.isFinite(n) ? { lump_sum_available: n } : null;
}

function VoiceInterviewCard({ caseId }: { caseId: string | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  // Offline → the manual card is the whole interview, so open it immediately.
  const [cardOpen, setCardOpen] = useState(!INTAKE_AGENT_ID);
  const [heard, setHeard] = useState<FinancialProfileInput>({});

  useEffect(() => {
    if (!INTAKE_AGENT_ID) return;
    const el = containerRef.current;
    if (!el) return;
    const onEnd = (e: Event) => {
      const heardNow = extractHeard(e);
      if (heardNow) setHeard((h) => ({ ...h, ...heardNow }));
      setCardOpen(true);
    };
    // The widget's end-event name isn't guaranteed — listen to the plausible
    // set so the confirmation card reliably appears when the call finishes.
    const endEvents = [
      "elevenlabs-convai:call-ended",
      "elevenlabs-convai:disconnect",
      "conversation-ended",
      "call-ended",
      "disconnect",
      "ended",
    ];
    endEvents.forEach((name) => el.addEventListener(name, onEnd));
    return () => endEvents.forEach((name) => el.removeEventListener(name, onEnd));
  }, []);

  const confirming = !!INTAKE_AGENT_ID && heard.lump_sum_available != null;

  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 16 }}>
        <h3 style={{ fontSize: 17 }}>A two-minute conversation</h3>
        <span className="pill pill-muted">~2 min</span>
      </div>
      <p style={{ fontSize: 14, color: "var(--text-secondary)", margin: "8px 0 16px", lineHeight: 1.6 }}>
        Our intake agent asks only what your documents can&apos;t answer: household income and size,
        what you could put down today, and the most you could manage monthly. It never re-asks
        anything already on the bill.
      </p>

      {INTAKE_AGENT_ID ? (
        <div ref={containerRef}>
          <elevenlabs-convai agent-id={INTAKE_AGENT_ID} />
          <Script src="https://unpkg.com/@elevenlabs/convai-widget-embed" strategy="afterInteractive" />
          {!cardOpen && (
            <button
              type="button"
              onClick={() => setCardOpen(true)}
              style={{
                background: "none",
                border: "none",
                color: "var(--accent)",
                fontSize: 13,
                marginTop: 12,
                cursor: "pointer",
                textDecoration: "underline",
                padding: 0,
              }}
            >
              Prefer to type it — or confirm what we heard? Enter your numbers →
            </button>
          )}
        </div>
      ) : (
        <p className="todo" style={{ marginBottom: 16 }}>
          The voice interview is taking a break. Enter the numbers below and we&apos;ll take it from there.
        </p>
      )}

      {cardOpen && <ManualFinancialCard caseId={caseId} prefill={heard} confirming={confirming} />}
    </div>
  );
}

function toNumber(s: string): number | undefined {
  const n = parseFloat(s.replace(/[^0-9.]/g, ""));
  return Number.isFinite(n) ? n : undefined;
}

function ManualFinancialCard({
  caseId,
  prefill,
  confirming,
}: {
  caseId: string | null;
  prefill: FinancialProfileInput;
  confirming: boolean;
}) {
  const [lump, setLump] = useState(prefill.lump_sum_available != null ? String(prefill.lump_sum_available) : "");
  const [monthly, setMonthly] = useState("");
  const [income, setIncome] = useState("");
  const [size, setSize] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "empty" | "error">("idle");
  const [floor, setFloor] = useState<number | null>(null);

  async function save() {
    if (!caseId) return;
    const fields: FinancialProfileInput = {};
    if (toNumber(lump) !== undefined) fields.lump_sum_available = toNumber(lump);
    if (toNumber(monthly) !== undefined) fields.monthly_max = toNumber(monthly);
    if (toNumber(income) !== undefined) fields.household_income = toNumber(income);
    if (toNumber(size) !== undefined) fields.household_size = toNumber(size);
    if (Object.keys(fields).length === 0) {
      setStatus("empty");
      return;
    }
    setStatus("saving");
    try {
      const res = await saveFinancialProfile(caseId, fields);
      setFloor(res.floor);
      setStatus("saved");
    } catch {
      setStatus("error");
    }
  }

  const label: React.CSSProperties = {
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--text-tertiary)",
    marginBottom: 4,
    display: "block",
  };
  const input: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid var(--border)",
    background: "var(--surface, transparent)",
    color: "var(--text-primary)",
    fontSize: 15,
  };

  const heading = confirming
    ? `We heard: you could put down ${money(prefill.lump_sum_available)} today — correct?`
    : "What could you put toward this?";

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: 16,
        marginTop: 8,
        background: "var(--surface-muted, rgba(0,0,0,0.02))",
      }}
    >
      <h4 style={{ fontSize: 15, margin: "0 0 4px" }}>{heading}</h4>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "0 0 16px" }}>
        These four numbers set your negotiating position — we never offer more than you can put down.
        Fill in what you can; adjust anything that&apos;s off.
      </p>

      <div style={{ marginBottom: 12 }}>
        <label htmlFor="fin-lump" style={label}>
          Most you could put down today
        </label>
        <input
          id="fin-lump"
          aria-label="Most you could put down today"
          inputMode="decimal"
          placeholder="$1,700"
          value={lump}
          onChange={(e) => setLump(e.target.value)}
          style={input}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
        <div>
          <label htmlFor="fin-monthly" style={label}>
            Most you could pay monthly
          </label>
          <input
            id="fin-monthly"
            aria-label="Most you could pay monthly"
            inputMode="decimal"
            placeholder="$150"
            value={monthly}
            onChange={(e) => setMonthly(e.target.value)}
            style={input}
          />
        </div>
        <div>
          <label htmlFor="fin-income" style={label}>
            Household income (yearly)
          </label>
          <input
            id="fin-income"
            aria-label="Household income yearly"
            inputMode="decimal"
            placeholder="$39,000"
            value={income}
            onChange={(e) => setIncome(e.target.value)}
            style={input}
          />
        </div>
        <div>
          <label htmlFor="fin-size" style={label}>
            People in household
          </label>
          <input
            id="fin-size"
            aria-label="People in household"
            inputMode="numeric"
            placeholder="2"
            value={size}
            onChange={(e) => setSize(e.target.value)}
            style={input}
          />
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={save}
          disabled={status === "saving" || !caseId}
          style={status === "saving" || !caseId ? { opacity: 0.7 } : undefined}
        >
          {status === "saving" ? "Saving…" : status === "saved" ? "Saved ✓" : "Save these numbers"}
        </button>
        {status === "saved" && (
          <span style={{ fontSize: 14, color: "var(--accent)" }}>
            {floor != null
              ? `Locked in — we'll never offer more than ${money(floor)} on your behalf.`
              : "Locked in — thanks."}
          </span>
        )}
        {status === "empty" && (
          <span style={{ fontSize: 14, color: "var(--flag)" }}>Enter at least one number first.</span>
        )}
        {status === "error" && (
          <span style={{ fontSize: 14, color: "var(--flag)" }}>
            We could not save that right now. Nothing was lost. Refresh in a moment and try again.
          </span>
        )}
      </div>
    </div>
  );
}
