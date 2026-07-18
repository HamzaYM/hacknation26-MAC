"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { confirmCase, getDemoCase, getFlags } from "../../lib/api";
import { facilitySavings, money } from "../../lib/savings";
import { FLAG_LABELS } from "../../lib/types";
import type { DerivedFlag, JobSpec } from "../../lib/types";

// PRD §11 screen 3 — the challenge-mandated gate: nothing dials until the
// user confirms this plan. Flags come from GET /cases/{id}/flags (computed
// live by the deterministic engine), not from a hardcoded list.
export default function Confirm() {
  const router = useRouter();
  const [spec, setSpec] = useState<JobSpec | null>(null);
  const [flags, setFlags] = useState<DerivedFlag[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState(false);

  useEffect(() => {
    getDemoCase()
      .then((s) => {
        setSpec(s);
        return getFlags(s.case_id).then((r) => setFlags(r.flags));
      })
      .catch(() => setLoadError(true));
  }, []);

  async function onConfirm() {
    if (!spec) return;
    setConfirming(true);
    setConfirmError(false);
    try {
      await confirmCase(spec.case_id);
      router.push("/bills");
    } catch {
      setConfirming(false);
      setConfirmError(true);
    }
  }

  if (loadError) {
    return (
      <p className="todo">
        Couldn&apos;t reach the API at :8000 — run <code>uvicorn app.main:app --reload --port 8000</code> in
        apps/api, then reload this page.
      </p>
    );
  }

  if (!spec || !flags) return <p className="todo">Loading your case…</p>;

  const savings = facilitySavings(spec);
  const estimateLow = savings.savedSoFar + savings.projectedLow;
  const estimateHigh = savings.savedSoFar + savings.projectedHigh;
  const pctLow = savings.percentSavedSoFar + savings.percentProjectedLow;
  const pctHigh = savings.percentSavedSoFar + savings.percentProjectedHigh;
  const totalFlagged = flags.reduce((sum, f) => sum + f.dollar_impact, 0);

  return (
    <div>
      <h1 style={{ marginTop: 16 }}>Here&apos;s the plan — confirm before we dial</h1>
      <p style={{ color: "var(--text-secondary)", margin: "8px 0 24px" }}>
        We read your bill and EOB from {spec.bill.facility_name}. Review what we found and what
        we&apos;ll argue — no call is placed until you approve.
      </p>

      <div className="card">
        <h3 style={{ marginBottom: 12 }}>Who we&apos;ll be negotiating with</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {spec.entities.map((entity) => (
            <span
              key={entity.name}
              className={`pill ${entity.kind === "facility" ? "pill-accent" : entity.kind === "collections" ? "pill-flag" : "pill-muted"}`}
            >
              {entity.name}
              {entity.balance != null && <span className="mono-figure">· {money(entity.balance)}</span>}
            </span>
          ))}
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 4 }}>{flags.length} problems found on this bill</h3>
        <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12 }}>
          Total flagged: <span className="mono-figure" style={{ color: "var(--flag)" }}>{money(totalFlagged)}</span>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {flags.map((flag, i) => (
            <span className="pill pill-flag" key={i}>
              {FLAG_LABELS[flag.type]}
              <span className="mono-figure">+{money(flag.dollar_impact)}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 4 }}>What that&apos;s worth</h3>
        <div className="mono-figure" style={{ fontSize: 26, color: "var(--accent)", margin: "8px 0 4px" }}>
          {money(estimateLow)}–{money(estimateHigh)}
        </div>
        <div style={{ fontSize: 14, color: "var(--text-secondary)" }}>
          Estimated savings if the calls go our way — {pctLow}–{pctHigh}% off your {money(savings.originalBalance)} balance.
        </div>
      </div>

      {confirmError && (
        <p className="todo">
          Couldn&apos;t confirm the plan — the API at :8000 didn&apos;t answer. Nothing was dialed; try again.
        </p>
      )}

      <div style={{ marginTop: 24, textAlign: "center" }}>
        <button className="btn btn-primary" onClick={onConfirm} disabled={confirming} style={confirming ? { opacity: 0.7 } : undefined}>
          {confirming ? "Confirming…" : "Looks right — make the calls"}
        </button>
        <div style={{ fontSize: 13, color: "var(--text-tertiary)", marginTop: 8 }}>
          Nothing gets dialed until you approve this plan.
        </div>
      </div>
    </div>
  );
}
