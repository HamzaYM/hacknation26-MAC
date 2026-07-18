"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import UploadCard from "../../components/UploadCard";

// Two separate authorized-rep grants, not one — per the research brief, calls
// split roughly 63/37 to providers vs. insurers, and insurer contact is its
// own required path whenever a bill and EOB disagree, a claim is denied, or
// an appeal needs filing (not just a courtesy CC). Treating "insurer" as an
// afterthought under a single HIPAA release was the gap.
const AUTH_ROWS = [
  { key: "hipaa_roi", label: "HIPAA release", detail: "Lets us request your itemized records and medical documentation" },
  { key: "provider_rep", label: "Provider authorized-representative", detail: "Lets us call and negotiate with hospital & doctor billing offices on your behalf" },
  { key: "insurer_rep", label: "Insurer authorized-representative", detail: "Lets us call your health plan — dispute denials, fix claim errors, and file appeals" },
  { key: "recording_consent", label: "Call-recording consent", detail: "Required to record negotiation calls" },
];

// Demo statuses — real values come from job_spec.authorizations once persistence lands (Hamza TODO).
const DEMO_STATUS: Record<string, "Confirmed" | "Submitted" | "Pending"> = {
  hipaa_roi: "Confirmed",
  provider_rep: "Confirmed",
  insurer_rep: "Submitted",
  recording_consent: "Pending",
};

export default function Onboard() {
  const router = useRouter();
  const [income, setIncome] = useState("$30k – $50k");
  // Gate: a brand-new case has nothing to negotiate until a bill exists.
  // Returning users who already have a case on file can skip past this —
  // that's the "already set up" escape hatch below, not a second upload gate.
  const [hasBill, setHasBill] = useState(false);
  const [skippingUpload, setSkippingUpload] = useState(false);
  const canContinue = hasBill || skippingUpload;

  return (
    <div className="card" style={{ maxWidth: 640, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>Step 1 of 1</span>
        <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>takes ~3 min</span>
      </div>
      <h1 style={{ fontSize: 30, marginBottom: 8 }}>Let&apos;s set up your case</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24 }}>
        A few details so our agents can act on your behalf. We only ask for what&apos;s needed to
        negotiate — nothing more.
      </p>

      <h3 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-tertiary)", marginBottom: 12 }}>
        Your first bill <span style={{ color: "var(--destructive)" }}>*</span>
      </h3>
      {!skippingUpload && (
        <UploadCard
          title="Upload a bill to get started"
          hint="A PDF or photo of any medical bill — we'll find the rest as we go"
          onSelect={() => setHasBill(true)}
        />
      )}
      {!hasBill && !skippingUpload && (
        <button
          type="button"
          onClick={() => setSkippingUpload(true)}
          style={{ background: "none", border: "none", color: "var(--text-tertiary)", fontSize: 13, marginTop: 8, cursor: "pointer", textDecoration: "underline" }}
        >
          I already have a case set up — skip this
        </button>
      )}
      {skippingUpload && (
        <p className="todo" style={{ marginTop: 8 }}>
          Skipping upload — assuming an existing case already has a bill on file. New cases need at
          least one before we can negotiate anything.
        </p>
      )}

      <h3 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-tertiary)", margin: "24px 0 12px" }}>
        Your details
      </h3>
      <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>Full name</label>
      <input defaultValue="Maya Chen" style={inputStyle} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>Date of birth</label>
          <input defaultValue="03 / 14 / 1995" className="mono" style={inputStyle} />
        </div>
        <div>
          <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>Phone</label>
          <input defaultValue="" placeholder="(___) ___-____" className="mono" style={inputStyle} />
        </div>
      </div>
      <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>Hospital account / member ID</label>
      <input defaultValue="MG-4471983" className="mono" style={inputStyle} />

      <h3 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-tertiary)", margin: "24px 0 12px" }}>
        Authorizations
      </h3>
      <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-card)" }}>
        {AUTH_ROWS.map((row, i) => (
          <div
            key={row.key}
            style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "16px", borderTop: i > 0 ? "1px solid var(--border)" : "none",
            }}
          >
            <div>
              <div style={{ fontWeight: 500 }}>{row.label}</div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{row.detail}</div>
            </div>
            <span className={`pill ${DEMO_STATUS[row.key] === "Confirmed" ? "pill-accent" : "pill-muted"}`}>
              {DEMO_STATUS[row.key]}
            </span>
          </div>
        ))}
      </div>

      <h3 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-tertiary)", margin: "24px 0 4px" }}>
        Financial snapshot <span style={{ textTransform: "none", letterSpacing: 0 }}>· optional, unlocks charity-care checks</span>
      </h3>
      <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>Household income band</label>
      <select value={income} onChange={(e) => setIncome(e.target.value)} style={inputStyle}>
        {["Under $30k", "$30k – $50k", "$50k – $75k", "$75k+"].map((v) => (
          <option key={v}>{v}</option>
        ))}
      </select>

      <button
        type="button"
        className="btn btn-primary"
        style={{ width: "100%", marginTop: 16 }}
        disabled={!canContinue}
        onClick={() => router.push("/bills")}
      >
        Continue to your bills →
      </button>
      {!canContinue && (
        <p style={{ textAlign: "center", fontSize: 12, color: "var(--text-tertiary)", marginTop: 8 }}>
          Upload a bill above to continue
        </p>
      )}
      <p style={{ textAlign: "center", fontSize: 12, color: "var(--text-tertiary)", marginTop: 12 }}>
        🔒 Bank-level encryption · you can revoke access anytime
      </p>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "12px 16px",
  borderRadius: "var(--radius-input)",
  border: "1px solid var(--border)",
  fontFamily: "var(--font-body)",
  fontSize: 15,
  marginBottom: 16,
  marginTop: 4,
  background: "var(--bg-surface)",
};
