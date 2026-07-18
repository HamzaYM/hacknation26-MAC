"use client";

import { useRef, useState } from "react";

// Real file picker; actual parsing isn't wired to the OpenAI vision pipeline
// yet (data/pipeline/README.md — TODO J/Hamza), so a selected file just moves
// to a "ready to parse" state rather than silently doing nothing, which is
// what the old decorative (non-interactive) card did.
export default function UploadCard({
  title = "Upload a new bill",
  hint = "Drag a PDF or photo of a bill / EOB here",
  onSelect,
}: {
  title?: string;
  hint?: string;
  onSelect?: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  function handleFile(f: File | undefined | null) {
    if (!f) return;
    setFile(f);
    onSelect?.(f);
  }

  return (
    <button
      type="button"
      className={`upload-card ${dragOver ? "drag-over" : ""}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFile(e.dataTransfer.files?.[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,image/*"
        hidden
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {file ? (
        <>
          <strong style={{ color: "var(--accent-hover)", display: "block", marginBottom: 4 }}>
            ✓ {file.name}
          </strong>
          <span>Ready — parsing isn&apos;t wired to the vision pipeline yet, but your file&apos;s selected</span>
        </>
      ) : (
        <>
          <strong style={{ color: "var(--text-primary)", display: "block", marginBottom: 4 }}>{title}</strong>
          {hint}
        </>
      )}
    </button>
  );
}
