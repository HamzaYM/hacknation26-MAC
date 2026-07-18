"use client";

import { useEffect, useState } from "react";
import { getDemoCase } from "../../lib/api";
import { entitySavings, facilitySavings, money } from "../../lib/savings";
import { procedureLabel } from "../../lib/procedures";
import UploadCard from "../../components/UploadCard";
import type { JobSpec, Entity } from "../../lib/types";

export default function BillList() {
  const [spec, setSpec] = useState<JobSpec | null>(null);
  const [error, setError] = useState(false);

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
        <UploadCard />
      </div>

      {error && (
        <p className="todo">
          Couldn&apos;t reach the API at :8000 — run <code>uvicorn app.main:app --reload --port 8000</code> in
          apps/api. Showing nothing until it&apos;s up.
        </p>
      )}

      <div className="entity-grid">
        {spec?.entities.map((entity) => (
          <EntityCard key={entity.name} entity={entity} spec={spec} />
        ))}
      </div>
    </div>
  );
}

function EntityCard({ entity, spec }: { entity: Entity; spec: JobSpec }) {
  const isFacility = entity.kind === "facility";
  const savings = isFacility ? facilitySavings(spec) : entitySavings(entity);
  const flagCount = isFacility ? spec.derived_flags.length : null;
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
        <span className={`pill ${isFacility ? "pill-accent" : entity.kind === "collections" ? "pill-flag" : "pill-muted"}`}>
          {isFacility ? "In progress" : entity.kind === "collections" ? "Queued" : "Awaiting you"}
        </span>
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
            Typical range for this type of bill — {money(savings.projectedLow)}–{money(savings.projectedHigh)} possible
          </div>
        )}
      </div>
    </a>
  );
}
