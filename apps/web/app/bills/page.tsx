"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createCase, getMyCase, parseDocument } from "../../lib/api";
import type { ParseDocumentResponse } from "../../lib/api";
import { useSession } from "../../lib/auth";
import { entitySavings, facilitySavings, money } from "../../lib/savings";
import { procedureLabel } from "../../lib/procedures";
import { billStatus, sortByStatus, STATUS_META, type BillStatus } from "../../lib/billStatus";
import UploadCard from "../../components/UploadCard";
import ParsedDocPreview from "../../components/ParsedDocPreview";
import { DeadlineStrip, daysLeft } from "../../components/DeadlineStrip";
import type { JobSpec, Entity } from "../../lib/types";

const SECTION_ORDER: BillStatus[] = ["awaiting_you", "in_progress", "queued"];
const SECTION_LABEL: Record<BillStatus, string> = {
  awaiting_you: "Needs your attention",
  in_progress: "In progress",
  queued: "Queued",
};

// Per-bill next step, with the clock that governs it. Keyed off entity kind,
// same interim convention as billStatus() until real call state persists.
function nextLine(entity: Entity, spec: JobSpec): string {
  const sd = spec.bill.statement_date;
  switch (entity.kind) {
    case "facility":
      return sd
        ? `supervisor callback to press the benchmark anchor · GFE window ${Math.max(daysLeft(sd, 120), 0)}d`
        : "supervisor callback to press the benchmark anchor";
    case "er_physician_group":
      return sd
        ? `your income range unlocks the charity care ask · FAP window ${Math.max(daysLeft(sd, 240), 0)}d`
        : "your income range unlocks the charity care ask";
    case "collections":
      return sd
        ? `validation demand goes out · ${Math.max(daysLeft(sd, 30), 0)}d on the FDCPA clock`
        : "validation demand goes out before any offer";
    default:
      return "we review the plan with you before the first call";
  }
}

export default function BillList() {
  const session = useSession();
  const email = session?.user?.email;
  const router = useRouter();
  const [spec, setSpec] = useState<JobSpec | null>(null);
  const [error, setError] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    // Logged in → their case via cases.owner_email; logged out → Maya's demo
    // case (the session hydrates async, so refetch when the email appears).
    getMyCase(email ?? undefined).then(setSpec).catch(() => setError(true));
  }, [email]);

  const patientName = (spec?.patient?.legal_name as string) ?? "–";

  const totalSavedSoFar = spec
    ? spec.entities.reduce((sum, e) => sum + (e.kind === "facility" ? facilitySavings(spec).savedSoFar : 0), 0)
    : 0;
  const totalProjectedHigh = spec
    ? spec.entities.reduce(
        (sum, e) => sum + (e.kind === "facility" ? facilitySavings(spec).projectedHigh : entitySavings(e).projectedHigh),
        0
      )
    : 0;

  const sortedEntities = spec ? sortByStatus(spec.entities) : [];

  return (
    <div>
      <div className="user-strip">
        <span className="avatar">{patientName.charAt(0) || "?"}</span>
        <span><strong>{patientName}</strong></span>
        <span>· Boston, MA</span>
      </div>

      <div className="savings-hero">
        <div className="eyebrow">Across your {spec?.entities.length ?? "…"} active bills</div>
        <div className="figure mono-figure">{money(totalSavedSoFar + totalProjectedHigh)}</div>
        <div className="caption">in savings: {money(totalSavedSoFar)} locked in, up to {money(totalProjectedHigh)} more possible</div>
        <div className="subnote">Cash in anytime, per bill, or let us keep negotiating.</div>
      </div>

      {spec?.bill.statement_date && <DeadlineStrip statementDate={spec.bill.statement_date} />}

      <div style={{ marginBottom: 24 }}>
        {!creating ? (
          <button className="btn btn-secondary" style={{ width: "100%" }} onClick={() => setCreating(true)}>
            + Create new bill
          </button>
        ) : (
          <CreateBillPanel
            onCancel={() => setCreating(false)}
            onCreated={(caseId) => router.push(`/bills/${caseId}`)}
          />
        )}
      </div>

      {error && (
        <p className="todo">
          Couldn&apos;t reach the API at :8000. Run <code>uvicorn app.main:app --reload --port 8000</code> in
          apps/api. Showing nothing until it&apos;s up.
        </p>
      )}

      {SECTION_ORDER.map((status) => {
        const entities = sortedEntities.filter((e) => billStatus(e) === status);
        if (entities.length === 0) return null;
        return (
          <div key={status} style={{ marginBottom: 28 }}>
            <div className="section-label">
              <span className={`pill ${STATUS_META[status].pillClass}`}>{STATUS_META[status].label}</span>
            </div>
            <div className="entity-grid">
              {entities.map((entity) => spec && <EntityCard key={entity.name} entity={entity} spec={spec} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

type DocKind = "bill" | "eob";

type SlotState =
  | { status: "idle" }
  | { status: "parsing"; fileName: string }
  | { status: "error"; fileName: string; file: File }
  | { status: "done"; fileName: string; result: ParseDocumentResponse };

// Real upload → parse wiring: POST /cases (falls back to a client-generated
// id if that endpoint isn't live yet on this build — a parallel worktree
// is landing it) then POST /documents/parse per file against that case_id.
// Line items, reconciliation, and flags all come back from the real engine
// (ParsedDocPreview) — nothing here is simulated.
function CreateBillPanel({ onCancel, onCreated }: { onCancel: () => void; onCreated: (caseId: string) => void }) {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [slots, setSlots] = useState<Record<DocKind, SlotState>>({
    bill: { status: "idle" },
    eob: { status: "idle" },
  });

  async function ensureCaseId(): Promise<string> {
    if (caseId) return caseId;
    try {
      const { case_id } = await createCase();
      setCaseId(case_id);
      return case_id;
    } catch {
      // POST /cases isn't live on this build yet — fall back to a
      // client-generated id so the upload still lands somewhere; the case
      // itself won't resolve on /bills/[caseId] until that endpoint merges.
      const fallback =
        typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `case-${Date.now()}`;
      setCaseId(fallback);
      return fallback;
    }
  }

  function setSlot(kind: DocKind, state: SlotState) {
    setSlots((prev) => ({ ...prev, [kind]: state }));
  }

  async function parse(kind: DocKind, file: File) {
    setSlot(kind, { status: "parsing", fileName: file.name });
    try {
      const cid = await ensureCaseId();
      const result = await parseDocument(file, kind, cid);
      setSlot(kind, { status: "done", fileName: file.name, result });
    } catch {
      setSlot(kind, { status: "error", fileName: file.name, file });
    }
  }

  const anyDone = slots.bill.status === "done" || slots.eob.status === "done";

  return (
    <div className="card">
      <h3 style={{ fontSize: 15, marginBottom: 4 }}>New bill</h3>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12 }}>
        Upload the medical bill and EOB. One is enough to start, add the other later.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <BillDocSlot
          kind="bill"
          title="Medical bill"
          hint="The itemized bill from the provider"
          demoFile={{ url: "/demo-docs/mercy_general_bill.pdf", name: "mercy_general_bill.pdf" }}
          state={slots.bill}
          onFile={(f) => parse("bill", f)}
          onReset={() => setSlot("bill", { status: "idle" })}
        />
        <BillDocSlot
          kind="eob"
          title="Explanation of Benefits"
          hint="The EOB from your insurer"
          demoFile={{ url: "/demo-docs/bcbs_eob.pdf", name: "bcbs_eob.pdf" }}
          state={slots.eob}
          onFile={(f) => parse("eob", f)}
          onReset={() => setSlot("eob", { status: "idle" })}
        />
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {anyDone && caseId && (
          <button className="btn btn-primary" onClick={() => onCreated(caseId)}>
            View parsed bill →
          </button>
        )}
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function BillDocSlot({
  kind,
  title,
  hint,
  demoFile,
  state,
  onFile,
  onReset,
}: {
  kind: DocKind;
  title: string;
  hint: string;
  demoFile: { url: string; name: string };
  state: SlotState;
  onFile: (file: File) => void;
  onReset: () => void;
}) {
  if (state.status === "idle") {
    return <UploadCard title={title} hint={hint} onSelect={onFile} demoFile={demoFile} />;
  }
  if (state.status === "parsing") {
    return (
      <div className="document-card" style={{ marginBottom: 0 }}>
        <div className="document-icon">📄</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600 }}>{state.fileName}</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>
            <span className="live-dot" style={{ marginRight: 6 }}><span className="dot" /></span>
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
          Couldn&apos;t parse <strong>{state.fileName}</strong>. The API at :8000 didn&apos;t answer.
          Your file is still here; nothing was lost.
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-secondary" onClick={() => onFile(state.file)}>Try again</button>
          <button
            type="button"
            onClick={onReset}
            style={{ background: "none", border: "none", color: "var(--text-tertiary)", fontSize: 13, cursor: "pointer", textDecoration: "underline" }}
          >
            Choose a different file
          </button>
        </div>
      </div>
    );
  }
  return (
    <ParsedDocPreview kind={kind} fileName={state.fileName} result={state.result} onReset={onReset} />
  );
}

function EntityCard({ entity, spec }: { entity: Entity; spec: JobSpec }) {
  const isFacility = entity.kind === "facility";
  const savings = isFacility ? facilitySavings(spec) : entitySavings(entity);
  const flagCount = isFacility ? spec.derived_flags.length : null;
  const status = billStatus(entity);
  const barTotal = savings.percentSavedSoFar + savings.percentProjectedHigh;
  const achievedWidth = barTotal > 0 ? (savings.percentSavedSoFar / barTotal) * 100 : 0;
  const projectedWidth = barTotal > 0 ? (savings.percentProjectedHigh / barTotal) * 100 : 0;

  return (
    <a href={`/bills/${spec.case_id}`} className="entity-card">
      <div>
        <h3>{entity.name}</h3>
        <div className="meta">{procedureLabel(entity.name, entity.kind)} · Mar 2026</div>
      </div>
      <div className="balance-block">
        <span className={`pill ${STATUS_META[status].pillClass}`}>{STATUS_META[status].label}</span>
        <div className="balance-new mono-figure" style={{ marginTop: 6 }}>{money(savings.currentBalance)}</div>
        {savings.savedSoFar > 0 && <div className="balance-old mono-figure">{money(savings.originalBalance)}</div>}
      </div>

      <div className="savings-bar-wrap">
        <div className="savings-bar-label">
          <span>{savings.percentSavedSoFar}% saved so far</span>
          <span>up to {savings.percentSavedSoFar + savings.percentProjectedHigh}% possible</span>
        </div>
        <div className="savings-bar">
          <div className="achieved" style={{ width: `${achievedWidth}%` }} />
          <div className="projected" style={{ width: `${projectedWidth}%` }} />
        </div>
        {isFacility ? (
          <div className="issue-line" style={{ borderTop: "none", paddingTop: 8 }}>
            <strong>{flagCount} issues found</strong>, up to {money(savings.projectedHigh)} more on the table
          </div>
        ) : (
          <div className="issue-line" style={{ borderTop: "none", paddingTop: 8 }}>
            Based on our research and aggregated data on people like you: {money(savings.projectedLow)}–{money(savings.projectedHigh)} possible
          </div>
        )}
        <div style={{ marginTop: 6, fontSize: 12.5, color: "var(--text-secondary)" }}>
          <strong style={{ color: "var(--text-primary)" }}>Next:</strong> {nextLine(entity, spec)}
        </div>
      </div>
    </a>
  );
}
