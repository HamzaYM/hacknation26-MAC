"use client";

import { useEffect, useRef, useState } from "react";
import { getAuthorization, uploadAuthorization, type AuthorizationState } from "../lib/api";

// The consent moment. Maya records herself, on the platform, authorizing the AI
// advocate to discuss and negotiate her account. The agent presents THIS the
// moment a rep challenges authorization mid-call (it reads the recorded words
// verbatim; there is no way to play the clip into a live PSTN call). It is also
// paper-trail evidence, shown on the case file with the same statement text.
//
// Records via MediaRecorder; a file-input fallback keeps the upload path usable
// where MediaRecorder is unavailable (headless browsers, older devices) and for
// keyboard/AT users. Both paths hit the same POST /cases/{id}/authorization.

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}

type Phase = "idle" | "recording" | "recorded" | "uploading" | "on_file" | "error";

export default function RecordAuthorization({
  caseId,
  statement,
  patientName,
}: {
  caseId: string;
  statement: string;
  patientName: string;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [state, setState] = useState<AuthorizationState | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [canRecord, setCanRecord] = useState(true);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const blobRef = useRef<Blob | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load any existing on-file authorization so a re-visit shows the done state.
  useEffect(() => {
    getAuthorization(caseId)
      .then((s) => {
        if (s.on_file) {
          setState(s);
          setPhase("on_file");
        }
      })
      .catch(() => {});
    if (typeof window === "undefined" || typeof window.MediaRecorder === "undefined") {
      setCanRecord(false);
    }
  }, [caseId]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  async function startRecording() {
    setErrorMsg("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        blobRef.current = blob;
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setPreviewUrl(URL.createObjectURL(blob));
        setPhase("recorded");
      };
      recorderRef.current = rec;
      rec.start();
      setPhase("recording");
    } catch {
      setCanRecord(false);
      setErrorMsg("We couldn't reach your microphone. You can upload an audio file instead.");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
  }

  function reRecord() {
    blobRef.current = null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setPhase("idle");
  }

  function onFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    blobRef.current = f;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(f));
    setPhase("recorded");
  }

  async function submit() {
    if (!blobRef.current) return;
    setPhase("uploading");
    setErrorMsg("");
    try {
      const result = await uploadAuthorization(caseId, blobRef.current, statement);
      setState(result);
      setPhase("on_file");
    } catch {
      setErrorMsg("Upload failed. The API at :8000 didn't answer. Nothing was saved; try again.");
      setPhase("recorded");
    }
  }

  // ── Done: authorization on file ─────────────────────────────────────────
  if (phase === "on_file" && state) {
    return (
      <div className="card" style={{ borderColor: "var(--accent)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span
            aria-hidden
            style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 22, height: 22, borderRadius: "50%", background: "var(--accent)",
              color: "#fff", fontSize: 13, fontWeight: 700,
            }}
          >
            ✓
          </span>
          <h3 style={{ margin: 0 }}>Authorization on file</h3>
        </div>
        <p style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.55 }}>
          {patientName} recorded this{state.recorded_at ? ` on ${fmtDate(state.recorded_at)}` : ""}. If a
          billing rep asks whether we&apos;re authorized, the agent reads these exact words back and offers to
          send the recording and a written release. It never claims to play the audio over the phone.
        </p>
        {state.recording_url && (
          <audio controls src={state.recording_url} style={{ width: "100%", height: 36, marginBottom: 12 }} />
        )}
        <blockquote
          style={{
            margin: 0, padding: "10px 14px", borderLeft: "3px solid var(--accent)",
            background: "var(--surface-2, rgba(0,0,0,0.03))", borderRadius: 6,
            fontSize: 13.5, color: "var(--text-secondary)", lineHeight: 1.6, fontStyle: "italic",
          }}
        >
          {state.statement_text}
        </blockquote>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={reRecord}
          style={{ marginTop: 12, padding: "6px 16px", fontSize: 13 }}
        >
          Record again
        </button>
      </div>
    );
  }

  // ── Capture card ────────────────────────────────────────────────────────
  return (
    <div className="card">
      <h3 style={{ marginBottom: 4 }}>Record your authorization</h3>
      <p style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.55 }}>
        Some billing offices want to hear you approve this before they&apos;ll talk to us. Read the lines
        below out loud and record them once. If they ask on a call, our agent plays back your words and can
        send the recording plus a written release.
      </p>

      <blockquote
        style={{
          margin: "0 0 14px", padding: "12px 16px", borderLeft: "3px solid var(--accent)",
          background: "var(--surface-2, rgba(0,0,0,0.03))", borderRadius: 6,
          fontSize: 14, color: "var(--text-primary)", lineHeight: 1.65,
        }}
      >
        {statement}
      </blockquote>

      {previewUrl && (phase === "recorded" || phase === "uploading") && (
        <audio controls src={previewUrl} style={{ width: "100%", height: 36, marginBottom: 12 }} />
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        {phase === "idle" && canRecord && (
          <button type="button" className="btn btn-primary" onClick={startRecording} style={{ padding: "8px 18px" }}>
            ● Record
          </button>
        )}
        {phase === "recording" && (
          <button type="button" className="btn btn-primary" onClick={stopRecording} style={{ padding: "8px 18px" }}>
            ■ Stop recording
          </button>
        )}
        {phase === "recorded" && (
          <>
            <button type="button" className="btn btn-primary" onClick={submit} style={{ padding: "8px 18px" }}>
              Save authorization
            </button>
            <button type="button" className="btn btn-secondary" onClick={reRecord} style={{ padding: "8px 18px" }}>
              Re-record
            </button>
          </>
        )}
        {phase === "uploading" && (
          <button type="button" className="btn btn-primary" disabled style={{ padding: "8px 18px", opacity: 0.7 }}>
            Saving…
          </button>
        )}

        {/* Accessible fallback: always available (keyboard/AT users, and headless
            browsers where MediaRecorder is missing). */}
        {(phase === "idle" || phase === "recorded") && (
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              style={{ padding: "8px 18px", fontSize: 13 }}
            >
              Upload an audio file
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              aria-label="Upload an audio file of your authorization"
              hidden
              onChange={onFilePicked}
            />
          </>
        )}
      </div>

      {phase === "recording" && (
        <div style={{ marginTop: 10, fontSize: 13, color: "var(--flag)" }}>
          <span aria-hidden>●</span> Recording… read the lines above, then press Stop.
        </div>
      )}
      {errorMsg && <p style={{ marginTop: 10, marginBottom: 0, fontSize: 13, color: "var(--flag)" }}>{errorMsg}</p>}
    </div>
  );
}
