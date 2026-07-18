"use client";

import { useState } from "react";
import type { ActionItem } from "../lib/actionItems";

export default function ActionItemCard({
  item,
  onComplete,
  compact = false,
}: {
  item: ActionItem;
  onComplete: () => void;
  compact?: boolean;
}) {
  const [formValues, setFormValues] = useState<Record<string, string>>({});

  const formComplete =
    item.type === "form" && item.fields.every((f) => (formValues[f.key] ?? "").trim().length > 0);

  return (
    <div className={compact ? "action-card action-card-compact" : "action-card"}>
      <div className="eyebrow">Question · {item.entity}</div>
      <h2>{item.question}</h2>

      <div className="action-why">
        <strong>Why we&apos;re asking</strong>
        {item.why}
      </div>

      <div className="action-unlocks">
        <strong>Unlocks</strong>
        {item.unlocks}
      </div>

      {item.type === "confirm" && (
        <button className="btn btn-primary" style={{ width: "100%" }} onClick={onComplete}>
          Yes, go ahead
        </button>
      )}

      {item.type === "select" && (
        <div className="action-options">
          {item.options.map((opt) => (
            <button key={opt} className="action-option" onClick={onComplete}>
              {opt}
            </button>
          ))}
        </div>
      )}

      {item.type === "form" && (
        <>
          <div className="action-form-fields">
            {item.fields.map((f) => (
              <div key={f.key}>
                <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>{f.label}</label>
                {f.kind === "select" ? (
                  <select
                    className="action-form-input"
                    value={formValues[f.key] ?? ""}
                    onChange={(e) => setFormValues((v) => ({ ...v, [f.key]: e.target.value }))}
                  >
                    <option value="" disabled>
                      Select…
                    </option>
                    {f.options!.map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="action-form-input"
                    type="number"
                    placeholder={f.placeholder}
                    value={formValues[f.key] ?? ""}
                    onChange={(e) => setFormValues((v) => ({ ...v, [f.key]: e.target.value }))}
                  />
                )}
              </div>
            ))}
          </div>
          <button className="btn btn-primary" style={{ width: "100%" }} disabled={!formComplete} onClick={onComplete}>
            {item.submitLabel}
          </button>
        </>
      )}
    </div>
  );
}
