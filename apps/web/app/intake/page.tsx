"use client";

import { useState } from "react";
import Script from "next/script";
import UploadCard from "../../components/UploadCard";
import { parseDocument } from "../../lib/api";
import type { ParseDocumentResponse, Reconciliation } from "../../lib/api";
import { money } from "../../lib/savings";
import { FLAG_LABELS } from "../../lib/types";

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
    hint: "Drag the EOB from your insurer here — it lets us verify what the hospital billed",
  },
};

export default function Intake() {
  const [slots, setSlots] = useState<Record<DocKind, SlotState>>({
    bill: { status: "idle" },
    eob: { status: "idle" },
  });

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
      <p style={{ color: "var(--text-secondary)", marginBottom: 24 }}>
        We read the bill and EOB line by line, check them against your case records, and flag
        anything worth arguing. Then a short voice interview covers what documents can&apos;t tell us.
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
        <VoiceInterviewCard />
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
            Reading the document — extracting line items and checking them against your case records…
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
          Couldn&apos;t parse <strong>{state.fileName}</strong> — the API at :8000 didn&apos;t answer.
          Your file is still here; nothing was lost.
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

  return <ParseResult kind={kind} fileName={state.fileName} result={state.result} onReset={onReset} />;
}

function verdictPill(recon: Reconciliation) {
  if (recon.verdict === "exact") return { cls: "pill-accent", label: "Matches your case records" };
  if (recon.verdict === "partial")
    return {
      cls: "pill-flag",
      label: `Partial match · ${recon.mismatches.length} difference${recon.mismatches.length === 1 ? "" : "s"}`,
    };
  return { cls: "pill-flag", label: "Doesn't match your case records" };
}

// Mismatch values arrive untyped (numbers are dollar amounts in this contract).
function fmtValue(v: unknown) {
  if (typeof v === "number") return money(v);
  if (v == null) return "—";
  return String(v);
}

function ParseResult({
  kind,
  fileName,
  result,
  onReset,
}: {
  kind: DocKind;
  fileName: string;
  result: ParseDocumentResponse;
  onReset: () => void;
}) {
  const { parsed, reconciliation, flags } = result;
  const pill = verdictPill(reconciliation);
  const balance = kind === "bill" ? parsed.patient_balance : parsed.patient_responsibility_total;
  const balanceLabel = kind === "bill" ? "Your balance" : "Patient responsibility";
  const cell: React.CSSProperties = { padding: "8px 0", borderTop: "1px solid var(--border)", fontSize: 14 };

  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div className="document-icon">📄</div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ fontWeight: 600 }}>{fileName}</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 2 }}>
            {parsed.line_items.length} line item{parsed.line_items.length === 1 ? "" : "s"} extracted ·{" "}
            {reconciliation.matches} verified against your case records
          </div>
        </div>
        <span className={`pill ${pill.cls}`}>{pill.label}</span>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 16 }}>
        <thead>
          <tr>
            {["CPT", "Description", "Date", "Billed"].map((h, i) => (
              <th
                key={h}
                style={{
                  textAlign: i === 3 ? "right" : "left",
                  fontSize: 12,
                  fontWeight: 500,
                  letterSpacing: "0.02em",
                  textTransform: "uppercase",
                  color: "var(--text-tertiary)",
                  padding: "0 0 8px",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {parsed.line_items.map((li, i) => (
            <tr key={`${li.cpt}-${i}`}>
              <td className="mono-figure" style={{ ...cell, fontSize: 13, paddingRight: 16 }}>{li.cpt}</td>
              <td style={{ ...cell, paddingRight: 16 }}>
                {li.description ?? "—"}
                {li.dx_codes && li.dx_codes.length > 0 && (
                  <span className="mono" style={{ fontSize: 11, color: "var(--text-tertiary)", marginLeft: 8 }}>
                    dx {li.dx_codes.join(", ")}
                  </span>
                )}
              </td>
              <td style={{ ...cell, color: "var(--text-secondary)", fontSize: 13, paddingRight: 16, whiteSpace: "nowrap" }}>
                {li.date_of_service ?? "—"}
              </td>
              <td className="mono-figure" style={{ ...cell, textAlign: "right", whiteSpace: "nowrap" }}>
                {money(li.billed_amount)}
              </td>
            </tr>
          ))}
          <tr>
            <td colSpan={3} style={{ ...cell, fontWeight: 600 }}>
              Total billed
            </td>
            <td className="mono-figure" style={{ ...cell, textAlign: "right", fontWeight: 600 }}>
              {money(parsed.total_billed)}
            </td>
          </tr>
          {balance != null && (
            <tr>
              <td colSpan={3} style={{ ...cell, fontWeight: 600 }}>
                {balanceLabel}
              </td>
              <td className="mono-figure" style={{ ...cell, textAlign: "right", fontWeight: 600 }}>
                {money(balance)}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {reconciliation.mismatches.length > 0 && (
        <div className="finding-card" style={{ marginTop: 16, marginBottom: 0 }}>
          <strong style={{ fontSize: 13 }}>Where this differs from your case records</strong>
          {reconciliation.mismatches.map((m, i) => (
            <div key={i} className="finding-evidence">
              <span className="cpt" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>CPT {m.cpt}</span>{" "}
              · {m.field.replaceAll("_", " ")}: parsed {fmtValue(m.parsed)} vs. expected {fmtValue(m.expected)}
            </div>
          ))}
        </div>
      )}

      {flags.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h3
            style={{
              fontSize: 13,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--text-tertiary)",
              marginBottom: 8,
              fontFamily: "var(--font-body)",
            }}
          >
            {flags.length} finding{flags.length === 1 ? "" : "s"} worth arguing
          </h3>
          {flags.map((flag, i) => (
            <div className="finding-card" key={i} style={{ marginBottom: 8 }}>
              <div className="finding-head">
                <div>
                  {flag.cpt && <span className="cpt">CPT {flag.cpt} · </span>}
                  <strong>{FLAG_LABELS[flag.type] ?? flag.type}</strong>
                </div>
                <span className="impact">+{money(flag.dollar_impact)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onReset}
        style={{
          background: "none",
          border: "none",
          color: "var(--text-tertiary)",
          fontSize: 13,
          marginTop: 12,
          cursor: "pointer",
          textDecoration: "underline",
          padding: 0,
        }}
      >
        Upload a different file
      </button>
    </div>
  );
}

function VoiceInterviewCard() {
  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 16 }}>
        <h3 style={{ fontSize: 17 }}>A two-minute conversation</h3>
        <span className="pill pill-muted">~2 min</span>
      </div>
      <p style={{ fontSize: 14, color: "var(--text-secondary)", margin: "8px 0 16px", lineHeight: 1.6 }}>
        Our intake agent asks only what your documents can&apos;t answer — household income and size,
        what you could put down today, and the most you could manage monthly. It never re-asks
        anything already on the bill.
      </p>
      {INTAKE_AGENT_ID ? (
        <>
          <elevenlabs-convai agent-id={INTAKE_AGENT_ID} />
          <Script src="https://unpkg.com/@elevenlabs/convai-widget-embed" strategy="afterInteractive" />
        </>
      ) : (
        <p className="todo">
          Voice interview is offline — set <code>NEXT_PUBLIC_ELEVENLABS_AGENT_ID_INTAKE</code> in{" "}
          <code>apps/web/.env.local</code> (copy the value of <code>ELEVENLABS_AGENT_ID_INTAKE</code>)
          and restart the dev server.
        </p>
      )}
    </div>
  );
}
