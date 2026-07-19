"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { confirmCase, getActionPlan, getDemoCase, getFlags, launchCalls } from "../../lib/api";
import type { ActionPlanResponse } from "../../lib/api";
import { getVoicePref, voiceById } from "../../lib/voice";
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
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [plan, setPlan] = useState<ActionPlanResponse | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState(false);

  useEffect(() => {
    getDemoCase()
      .then((s) => {
        setSpec(s);
        void getVoicePref(s.case_id).then(setVoiceId);
        // Action Plan copy is best-effort (null on 404/older API) — the flags
        // view below renders either way, so a missing endpoint never blocks.
        getActionPlan(s.case_id).then(setPlan).catch(() => setPlan(null));
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
      // The button's promise: confirming launches the simulated calls, then the
      // War Room shows them dialing live. A launch failure must not strand the
      // user on a dead confirm screen — the case is already confirmed, so route
      // to the War Room either way (it renders whatever calls exist, or its idle
      // "waiting for the calls" state — nothing looks broken).
      try {
        await launchCalls(spec.case_id, { simulate: true });
      } catch {
        // swallow — routing to /warroom below is the graceful fallback
      }
      router.push("/warroom");
    } catch {
      setConfirming(false);
      setConfirmError(true);
    }
  }

  if (loadError) {
    return (
      <p className="todo">
        Couldn&apos;t reach the API at :8000. Run <code>uvicorn app.main:app --reload --port 8000</code> in
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

  // Prefer the server's Action Plan copy (numbers guaranteed verbatim from the
  // engine); fall back to the locally computed strings when it's unavailable.
  const copy = plan?.copy;

  return (
    <div>
      <h1 style={{ marginTop: 16 }}>{copy?.headline ?? "Here's the plan: confirm before we dial"}</h1>
      <p style={{ color: "var(--text-secondary)", margin: "8px 0 24px" }}>
        {copy?.summary ??
          `We read your bill and EOB from ${spec.bill.facility_name}. Review what we found and what we'll argue. We don't dial until you approve.`}
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
          {copy?.flag_chips
            ? copy.flag_chips.map((chip, i) => (
                <span className="pill pill-flag" key={i}>
                  {chip.label}
                </span>
              ))
            : flags.map((flag, i) => (
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
          {plan?.input.savings_estimate.low != null && plan?.input.savings_estimate.high != null
            ? `${money(plan.input.savings_estimate.low)}–${money(plan.input.savings_estimate.high)}`
            : `${money(estimateLow)}–${money(estimateHigh)}`}
        </div>
        <div style={{ fontSize: 14, color: "var(--text-secondary)" }}>
          {copy?.savings_line ??
            `Estimated savings if the calls go our way: ${pctLow}–${pctHigh}% off your ${money(savings.originalBalance)} balance.`}
        </div>
      </div>

      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--space-md)", flexWrap: "wrap" }}>
        <div>
          <h3 style={{ marginBottom: 4 }}>The voice we&apos;ll call in</h3>
          <div style={{ fontSize: 14, color: "var(--text-secondary)" }}>
            {voiceById(voiceId ?? undefined)?.name ?? "Adam"}
            <span style={{ color: "var(--text-tertiary)" }}> · {voiceById(voiceId ?? undefined)?.tagline ?? "assertive and unbudging"}</span>
          </div>
        </div>
        <a href="/voice" className="btn btn-secondary" style={{ padding: "8px 18px", fontSize: 14 }}>
          Change voice
        </a>
      </div>
      {copy?.per_call_descriptions && copy.per_call_descriptions.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: 12 }}>The calls we&apos;ll make</h3>
          <ul style={{ margin: 0, paddingLeft: 18, color: "var(--text-secondary)", fontSize: 14, lineHeight: 1.7 }}>
            {copy.per_call_descriptions.map((c, i) => (
              <li key={i}>{c.copy}</li>
            ))}
          </ul>
        </div>
      )}

      {copy?.timeline_copy && (
        <div className="card">
          <h3 style={{ marginBottom: 8 }}>Is it safe to wait?</h3>
          <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: 14 }}>{copy.timeline_copy}</p>
        </div>
      )}

      {confirmError && (
        <p className="todo">
          Couldn&apos;t confirm the plan. The API at :8000 didn&apos;t answer. Nothing was dialed; try again.
        </p>
      )}

      <div style={{ marginTop: 24, textAlign: "center" }}>
        <button className="btn btn-primary" onClick={onConfirm} disabled={confirming} style={confirming ? { opacity: 0.7 } : undefined}>
          {confirming ? "Confirming…" : "Looks right, make the calls"}
        </button>
        <div style={{ fontSize: 13, color: "var(--text-tertiary)", marginTop: 8 }}>
          {copy?.next_step_line ?? "Nothing gets dialed until you approve this plan."}
        </div>
      </div>
    </div>
  );
}
