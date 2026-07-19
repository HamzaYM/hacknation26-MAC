"use client";

import { useEffect, useState } from "react";

// A copyable reference/account/claim number. The patient reads these aloud on
// a phone call, so the value is mono ("traceable fact"), the label is a tiny
// uppercase prefix, and one tap copies it — the button flips to a checkmark
// for ~1.5s, mirroring the War Room drop-chip timeout pattern.
//
// `tone="dark"` recolors it for the War Room's dark panels; everywhere else the
// default light tone sits on the product's warm surfaces.
export default function ReferenceChip({
  label,
  value,
  tone = "light",
}: {
  label: string;
  value: string;
  tone?: "light" | "dark";
}) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(t);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {
      // clipboard blocked (insecure origin / denied) — leave the value visible
    }
  }

  return (
    <button
      type="button"
      className={`ref-chip ref-chip-${tone}${copied ? " is-copied" : ""}`}
      onClick={copy}
      title={`Copy ${label} ${value}`}
      aria-label={`Copy ${label} ${value}`}
    >
      <span className="ref-chip-label">{label}</span>
      <span className="ref-chip-value mono">{value}</span>
      <span className="ref-chip-icon" aria-hidden>
        {copied ? "✓ copied" : "copy"}
      </span>
    </button>
  );
}
