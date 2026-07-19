"use client";

import { useState } from "react";
import type { Anchor } from "../lib/types";
import { money } from "../lib/savings";

// Tiered provenance (decision #15): a clean consumer face by default, with a
// "Show evidence" toggle that reveals every anchor's label/source/formula/
// source_url. Reusable across the dossier's multiples table and the War Room
// (e.g. next to a quoted benchmark on a live call card).
export default function EvidenceToggle({
  anchors,
  dark = false,
}: {
  anchors: Anchor[];
  /** War Room's panels sit on a dark background; the dossier is light. */
  dark?: boolean;
}) {
  const [open, setOpen] = useState(false);
  if (!anchors || anchors.length === 0) return null;

  const linkColor = dark ? "rgba(245,241,236,0.6)" : "var(--text-tertiary)";
  const panelBg = dark ? "rgba(255,255,255,0.04)" : "var(--bg-surface-muted)";
  const panelBorder = dark ? "1px solid rgba(245,241,236,0.12)" : "1px solid var(--border)";

  return (
    <div style={{ marginTop: open ? 8 : 0 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        data-testid="evidence-toggle"
        style={{
          background: "none",
          border: "none",
          padding: 0,
          cursor: "pointer",
          fontSize: 12,
          color: linkColor,
          textDecoration: "underline",
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
        }}
      >
        {open ? "Hide evidence" : "Show evidence"} <span style={{ fontSize: 10 }}>{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div
          data-testid="evidence-panel"
          style={{
            marginTop: 8,
            padding: "10px 12px",
            borderRadius: 10,
            background: panelBg,
            border: panelBorder,
          }}
        >
          {anchors.map((a, i) => (
            <div
              key={`${a.method}-${i}`}
              data-testid="evidence-anchor"
              data-confidence={a.confidence}
              style={{
                fontSize: 12.5,
                lineHeight: 1.6,
                paddingBottom: i < anchors.length - 1 ? 8 : 0,
                marginBottom: i < anchors.length - 1 ? 8 : 0,
                borderBottom: i < anchors.length - 1 ? panelBorder : "none",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, fontWeight: 600 }}>
                <span>{a.label}</span>
                <span className="mono-figure">{money(a.value)}</span>
              </div>
              <div style={{ color: linkColor, marginTop: 2 }}>
                {a.confidence} confidence
                {a.formula && <> · formula: <span className="mono">{a.formula}</span></>}
              </div>
              <div style={{ color: linkColor }}>
                source: {a.source}
                {a.source_url && (
                  <>
                    {" · "}
                    <a href={a.source_url} target="_blank" rel="noopener noreferrer" style={{ color: "inherit" }}>
                      view source ↗
                    </a>
                  </>
                )}
              </div>
              {a.band && (
                <div style={{ color: linkColor, marginTop: 2 }}>
                  band: p25 {money(a.band.p25)} · median {money(a.band.median)} · p75 {money(a.band.p75)} ·{" "}
                  {a.band.n_payers} payer{a.band.n_payers === 1 ? "" : "s"}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
