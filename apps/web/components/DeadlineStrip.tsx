"use client";

import { useState } from "react";

// ---- Regulatory deadline clocks, computed from the case's statement date ----
// Windows: FAP financial assistance (nonprofit hospitals, IRC §501(r): no
// extraordinary collection actions inside 240 days), GFE patient-provider
// dispute (No Surprises Act: 120 days from the bill date), FDCPA debt
// validation (30 days to demand the collector prove the debt, anchored to
// the statement date until real collector-contact dates persist).
//
// Each chip expands on click to a plain-English explanation plus a marker for
// who acts: the disputes we run ourselves ("Handled by us") vs. the charity
// application that needs the patient's income first ("Needs you").
type ClockOwner = "us" | "you";

interface ClockDef {
  id: string;
  label: string;
  days: number;
  plain: (daysRemaining: number) => string;
  owner: ClockOwner; // default; FAP is overridden by whether income is captured
}

const REGULATORY_CLOCKS: ClockDef[] = [
  {
    id: "fap",
    label: "FAP",
    days: 240,
    plain: (n) =>
      `Charity care application window: the hospital must accept your application for ${n} more days.`,
    owner: "you",
  },
  {
    id: "gfe",
    label: "GFE dispute",
    days: 120,
    plain: (n) => `You can dispute charges above the good-faith estimate for ${n} more days.`,
    owner: "us",
  },
  {
    id: "fdcpa",
    label: "FDCPA validation",
    days: 30,
    plain: (n) => `The collector must prove this debt if we demand it within ${n} days.`,
    owner: "us",
  },
];

const MS_PER_DAY = 86_400_000;

export function daysLeft(statementDate: string, windowDays: number): number {
  const start = new Date(`${statementDate}T00:00:00Z`).getTime();
  return Math.ceil((start + windowDays * MS_PER_DAY - Date.now()) / MS_PER_DAY);
}

export function DeadlineStrip({
  statementDate,
  financialProfileCaptured,
}: {
  statementDate: string;
  // FAP is handled by us once we have the income info to file; until then it
  // needs the patient. Undefined = we don't know, so we mark it "Needs you".
  financialProfileCaptured?: boolean;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const statementLabel = new Date(`${statementDate}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });

  const openClock = REGULATORY_CLOCKS.find((c) => c.id === expanded);
  const ownerOf = (clock: ClockDef): ClockOwner =>
    clock.id === "fap" ? (financialProfileCaptured ? "us" : "you") : clock.owner;

  return (
    <div style={{ margin: "0 0 24px" }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: "0.02em", color: "var(--text-tertiary)" }}>
          Regulatory clocks · {statementLabel} statement
        </span>
        {REGULATORY_CLOCKS.map((clock) => {
          const left = daysLeft(statementDate, clock.days);
          const closing = left <= 30;
          const isOpen = expanded === clock.id;
          return (
            <button
              key={clock.id}
              type="button"
              onClick={() => setExpanded((cur) => (cur === clock.id ? null : clock.id))}
              aria-expanded={isOpen}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 7,
                background: isOpen ? "var(--bg-surface-muted)" : "var(--bg-surface)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-pill)",
                padding: "5px 12px",
                fontSize: 12.5,
                fontFamily: "inherit",
                color: "var(--text-primary)",
                cursor: "pointer",
              }}
            >
              <strong style={{ fontWeight: 600 }}>{clock.label}</strong>
              <span
                className="mono-figure"
                style={{ fontSize: 12, fontWeight: 600, color: closing ? "var(--flag)" : "var(--text-secondary)" }}
              >
                {left > 0 ? `${left}d left` : "closed"}
              </span>
              <span style={{ color: "var(--text-tertiary)", fontSize: 11 }} aria-hidden>
                {isOpen ? "▾" : "▸"}
              </span>
            </button>
          );
        })}
      </div>

      {openClock && (
        <div
          style={{
            marginTop: 10,
            padding: "12px 14px",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-card)",
            maxWidth: 560,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
            <strong style={{ fontSize: 13 }}>{openClock.label}</strong>
            <span className={`pill ${ownerOf(openClock) === "us" ? "pill-accent" : "pill-warning"}`}>
              {ownerOf(openClock) === "us" ? "Handled by us" : "Needs you"}
            </span>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
            {(() => {
              const left = daysLeft(statementDate, openClock.days);
              if (left <= 0) return "This window has closed.";
              const base = openClock.plain(left);
              if (openClock.id === "fap" && ownerOf(openClock) === "you") {
                return `${base} We file it for you once you give us your household income and size.`;
              }
              return base;
            })()}
          </p>
        </div>
      )}
    </div>
  );
}
