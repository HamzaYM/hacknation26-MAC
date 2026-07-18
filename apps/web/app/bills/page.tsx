"use client";

import { useEffect, useState } from "react";
import { getDemoCase } from "../../lib/api";
import { entitySavings, facilitySavings, money } from "../../lib/savings";
import { procedureLabel } from "../../lib/procedures";
import { billStatus, sortByStatus, STATUS_META, type BillStatus } from "../../lib/billStatus";
import UploadCard from "../../components/UploadCard";
import type { JobSpec, Entity } from "../../lib/types";

interface PendingBill {
  id: string;
  docNames: string[];
  parsing: boolean;
}

const SECTION_ORDER: BillStatus[] = ["awaiting_you", "in_progress", "queued"];
const SECTION_LABEL: Record<BillStatus, string> = {
  awaiting_you: "Needs your attention",
  in_progress: "In progress",
  queued: "Queued",
};

export default function BillList() {
  const [spec, setSpec] = useState<JobSpec | null>(null);
  const [error, setError] = useState(false);
  const [pendingBills, setPendingBills] = useState<PendingBill[]>([]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    getDemoCase().then(setSpec).catch(() => setError(true));
  }, []);

  const patientName = (spec?.patient?.legal_name as string) ?? "—";

  const totalSavedSoFar = spec
    ? spec.entities.reduce((sum, e) => sum + (e.kind === "facility" ? facilitySavings(spec).savedSoFar : 0), 0)
    : 0;
  const totalProjectedHigh = spec
    ? spec.entities.reduce(
        (sum, e) => sum + (e.kind === "facility" ? facilitySavings(spec).projectedHigh : entitySavings(e).projectedHigh),
        0
      )
    : 0;

  function addPendingBill(docNames: string[]) {
    const id = `pending-${Date.now()}`;
    setPendingBills((prev) => [...prev, { id, docNames, parsing: false }]);
    setCreating(false);
    // "start parsing" — simulated; real extraction isn't wired to the vision
    // pipeline yet (data/pipeline/README.md TODO J/Hamza). This never
    // claims to finish, since we have nothing real to show once it "does."
    setTimeout(() => {
      setPendingBills((prev) => prev.map((b) => (b.id === id ? { ...b, parsing: true } : b)));
    }, 900);
  }

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
        <div className="caption">in savings — {money(totalSavedSoFar)} locked in, up to {money(totalProjectedHigh)} more possible</div>
        <div className="subnote">Cash in anytime, per bill, or let us keep negotiating.</div>
      </div>

      <div style={{ marginBottom: 24 }}>
        {!creating ? (
          <button className="btn btn-secondary" style={{ width: "100%" }} onClick={() => setCreating(true)}>
            + Create new bill
          </button>
        ) : (
          <CreateBillPanel onCancel={() => setCreating(false)} onCreate={addPendingBill} />
        )}
      </div>

      {error && (
        <p className="todo">
          Couldn&apos;t reach the API at :8000 — run <code>uvicorn app.main:app --reload --port 8000</code> in
          apps/api. Showing nothing until it&apos;s up.
        </p>
      )}

      {SECTION_ORDER.map((status) => {
        const entities = sortedEntities.filter((e) => billStatus(e) === status);
        const pendingHere = status === "queued" ? pendingBills : [];
        if (entities.length === 0 && pendingHere.length === 0) return null;
        return (
          <div key={status} style={{ marginBottom: 28 }}>
            <div className="section-label">
              <span className={`pill ${STATUS_META[status].pillClass}`}>{STATUS_META[status].label}</span>
            </div>
            <div className="entity-grid">
              {entities.map((entity) => spec && <EntityCard key={entity.name} entity={entity} spec={spec} />)}
              {pendingHere.map((pb) => (
                <PendingBillCard key={pb.id} bill={pb} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CreateBillPanel({ onCancel, onCreate }: { onCancel: () => void; onCreate: (docNames: string[]) => void }) {
  const [bill, setBill] = useState<string | null>(null);
  const [eob, setEob] = useState<string | null>(null);
  const canCreate = bill || eob;

  return (
    <div className="card">
      <h3 style={{ fontSize: 15, marginBottom: 4 }}>New bill</h3>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12 }}>
        Upload the medical bill and EOB — one is enough to start, add the other later.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <UploadCard
          title="Medical bill"
          hint="The itemized bill from the provider"
          onSelect={(f) => setBill(f.name)}
          demoFile={{ url: "/demo-docs/mercy_general_bill.pdf", name: "mercy_general_bill.pdf" }}
        />
        <UploadCard
          title="Explanation of Benefits"
          hint="The EOB from your insurer"
          onSelect={(f) => setEob(f.name)}
          demoFile={{ url: "/demo-docs/bcbs_eob.pdf", name: "bcbs_eob.pdf" }}
        />
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="btn btn-primary"
          disabled={!canCreate}
          onClick={() => onCreate([bill, eob].filter((x): x is string => !!x))}
        >
          Create bill
        </button>
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function PendingBillCard({ bill }: { bill: PendingBill }) {
  return (
    <div className="entity-card" style={{ cursor: "default" }}>
      <div>
        <h3>New bill</h3>
        <div className="meta">{bill.docNames.join(", ")}</div>
      </div>
      <div className="balance-block">
        <span className="pill pill-muted">Queued</span>
      </div>
      <div className="issue-line" style={{ borderTop: "none", paddingTop: 8 }}>
        {bill.parsing ? (
          <span><span className="live-dot" style={{ marginRight: 6 }}><span className="dot" /></span>Parsing your documents…</span>
        ) : (
          "Uploaded — starting parse"
        )}
      </div>
    </div>
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
            <strong>{flagCount} issues found</strong> — up to {money(savings.projectedHigh)} more on the table
          </div>
        ) : (
          <div className="issue-line" style={{ borderTop: "none", paddingTop: 8 }}>
            Based on our research and aggregated data on people like you — {money(savings.projectedLow)}–{money(savings.projectedHigh)} possible
          </div>
        )}
      </div>
    </a>
  );
}
