"use client";

import { useRef, useState } from "react";

// Real file picker; actual parsing isn't wired to the OpenAI vision pipeline
// yet (data/pipeline/README.md — TODO J/Hamza), so a selected file just moves
// to a "ready to parse" state rather than silently doing nothing, which is
// what the old decorative (non-interactive) card did.
//
// Every path (real picker, drag-drop, demo file) routes through a preview
// modal before the file counts as "selected" — for a demo, seeing the actual
// document pop up and confirming it is what makes the upload gesture read as
// real, rather than a file just silently appearing on the card.
export default function UploadCard({
  title = "Upload a new bill",
  hint = "Drag a PDF or photo of a bill / EOB here",
  onSelect,
  demoFile,
}: {
  title?: string;
  hint?: string;
  onSelect?: (file: File) => void;
  /** Lets a demo run without a real file picker gesture — previews a real
   * PDF from data/demo_docs/ (mirrored into public/demo-docs/) and, once
   * confirmed, hands it to the same handleFile path a real upload would. */
  demoFile?: { url: string; name: string };
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState<{ url: string; name: string; pendingFile?: File } | null>(null);

  function previewLocalFile(f: File | undefined | null) {
    if (!f) return;
    setPreview({ url: URL.createObjectURL(f), name: f.name, pendingFile: f });
  }

  function previewDemoFile(e: React.MouseEvent) {
    e.stopPropagation();
    if (!demoFile) return;
    setPreview({ url: demoFile.url, name: demoFile.name });
  }

  async function confirmAttach() {
    if (!preview) return;
    const finalFile =
      preview.pendingFile ?? new File([await (await fetch(preview.url)).blob()], preview.name, { type: "application/pdf" });
    setFile(finalFile);
    onSelect?.(finalFile);
    setPreview(null);
  }

  return (
    <>
      <button
        type="button"
        className={`upload-card ${dragOver ? "drag-over" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          previewLocalFile(e.dataTransfer.files?.[0]);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,image/*"
          hidden
          onChange={(e) => previewLocalFile(e.target.files?.[0])}
        />
        {file ? (
          <>
            <strong style={{ color: "var(--accent-hover)", display: "block", marginBottom: 4 }}>
              ✓ {file.name}
            </strong>
            <span>Ready. Parsing isn&apos;t wired to the vision pipeline yet, but your file&apos;s selected</span>
          </>
        ) : (
          <>
            <strong style={{ color: "var(--text-primary)", display: "block", marginBottom: 4 }}>{title}</strong>
            {hint}
            {demoFile && (
              <div style={{ marginTop: 10 }}>
                <span
                  role="button"
                  tabIndex={0}
                  onClick={previewDemoFile}
                  data-testid="use-demo-file"
                  style={{ fontSize: 12, color: "var(--accent-hover)", textDecoration: "underline", cursor: "pointer" }}
                >
                  or use the demo file ({demoFile.name})
                </span>
              </div>
            )}
          </>
        )}
      </button>

      {preview && (
        <div className="upload-preview-overlay" onClick={() => setPreview(null)}>
          <div className="upload-preview-modal" onClick={(e) => e.stopPropagation()}>
            <div className="upload-preview-header">
              <span className="mono-figure">{preview.name}</span>
              <button className="upload-preview-close" onClick={() => setPreview(null)} aria-label="Close preview">
                ✕
              </button>
            </div>
            <iframe src={preview.url} title={preview.name} className="upload-preview-frame" />
            <div className="upload-preview-actions">
              <button className="btn btn-primary" onClick={confirmAttach} data-testid="attach-document">
                Attach this document
              </button>
              <button className="btn btn-secondary" onClick={() => setPreview(null)}>
                Choose a different file
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
