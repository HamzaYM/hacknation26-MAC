"use client";

import { useEffect, useState } from "react";
import { listScenarios, loadScenario } from "../lib/api";
import type { ScenarioSummary } from "../lib/types";

const ARCHETYPE_LABELS: Record<string, string> = {
  maya_baseline: "Baseline",
  duplicate_charge: "Duplicate charge",
  upcoded_er: "Upcoded ER visit",
  unbundled_panel: "Unbundled panel",
  self_pay_gross: "Self-pay, gross charges",
  eob_mismatch: "EOB mismatch",
  oon_balance_bill: "Out-of-network balance bill",
  clean_overpriced: "Clean but overpriced",
  denial_driven: "Denial-driven",
};

// War Room scenario gallery (decision #11): lists GET /scenarios, and
// selecting one POSTs /scenarios/{id}/load then hands the resulting case_id
// to the caller, which drives the same War Room board for that case. Both
// calls degrade gracefully — listScenarios() never throws (empty array =
// empty state), loadScenario() failures surface inline without crashing the
// page, since WS3/WS4 are landing these endpoints in parallel worktrees.
export default function ScenarioPicker({
  onLoaded,
  dark = true,
}: {
  onLoaded: (caseId: string) => void;
  dark?: boolean;
}) {
  const [scenarios, setScenarios] = useState<ScenarioSummary[] | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listScenarios().then(setScenarios);
  }, []);

  async function pick(scenarioId: string) {
    setError(null);
    setLoadingId(scenarioId);
    try {
      const { case_id } = await loadScenario(scenarioId);
      onLoaded(case_id);
    } catch {
      setError("Couldn't load that scenario — the scenarios API isn't up yet on this build.");
    } finally {
      setLoadingId(null);
    }
  }

  const textColor = dark ? "rgba(245,241,236,0.85)" : "var(--text-primary)";
  const mutedColor = dark ? "rgba(245,241,236,0.5)" : "var(--text-secondary)";
  const border = dark ? "1px solid rgba(245,241,236,0.14)" : "1px solid var(--border)";
  const cardBg = dark ? "rgba(255,255,255,0.03)" : "var(--bg-surface)";

  if (scenarios === null) {
    return (
      <p data-testid="scenario-picker-loading" style={{ fontSize: 13, color: mutedColor }}>
        Loading scenarios…
      </p>
    );
  }

  if (scenarios.length === 0) {
    return (
      <p data-testid="scenario-picker-empty" style={{ fontSize: 13, color: mutedColor }}>
        No scenarios published yet. The 9-scenario suite (Maya + 8 archetypes) lands from the scenario
        generator; this gallery will populate as soon as it does.
      </p>
    );
  }

  return (
    <div data-testid="scenario-picker">
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 10,
        }}
      >
        {scenarios.map((s) => (
          <button
            key={s.scenario_id}
            type="button"
            data-testid="scenario-card"
            data-scenario-id={s.scenario_id}
            onClick={() => pick(s.scenario_id)}
            disabled={loadingId !== null}
            style={{
              textAlign: "left",
              cursor: loadingId ? "default" : "pointer",
              border,
              background: cardBg,
              borderRadius: 12,
              padding: 12,
              color: textColor,
              opacity: loadingId && loadingId !== s.scenario_id ? 0.5 : 1,
            }}
          >
            <div style={{ fontSize: 11, color: mutedColor, marginBottom: 4 }}>
              {ARCHETYPE_LABELS[s.archetype] ?? s.archetype}
            </div>
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 6 }}>{s.title}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {s.hospital?.name && (
                <span className="pill pill-muted" style={{ fontSize: 10.5 }}>{s.hospital.name}</span>
              )}
              {s.coverage?.payer_name ? (
                <span className="pill pill-muted" style={{ fontSize: 10.5 }}>{s.coverage.payer_name}</span>
              ) : s.coverage?.status === "self_pay" ? (
                <span className="pill pill-muted" style={{ fontSize: 10.5 }}>Self-pay</span>
              ) : null}
            </div>
            {loadingId === s.scenario_id && (
              <div style={{ fontSize: 11.5, marginTop: 8, color: mutedColor }}>Loading…</div>
            )}
          </button>
        ))}
      </div>
      {error && (
        <p style={{ fontSize: 12.5, color: dark ? "#f2a58f" : "var(--destructive)", marginTop: 10 }}>{error}</p>
      )}
    </div>
  );
}
