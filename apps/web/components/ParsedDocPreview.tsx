import type { ParseDocumentResponse, Reconciliation } from "../lib/api";
import { money } from "../lib/savings";
import { evidenceLine } from "../lib/evidence";
import { FLAG_LABELS } from "../lib/types";

// Renders a POST /documents/parse result: line items, the reconciliation
// verdict, and the flags the real engine found. Shared by the intake flow
// (apps/web/app/intake/page.tsx) and the new-bill "+ Create new bill" panel
// (apps/web/app/bills/page.tsx) so both surfaces show the same real parse
// output instead of two divergent renderers.
export function verdictPill(recon: Reconciliation) {
  if (recon.verdict === "exact") return { cls: "pill-accent", label: "Matches your case records" };
  if (recon.verdict === "partial")
    return {
      cls: "pill-flag",
      label: `Partial match · ${recon.mismatches.length} difference${recon.mismatches.length === 1 ? "" : "s"}`,
    };
  return { cls: "pill-flag", label: "Doesn't match your case records" };
}

// Mismatch values arrive untyped (numbers are dollar amounts in this contract).
function fmtValue(v: unknown) {
  if (typeof v === "number") return money(v);
  if (v == null) return "–";
  return String(v);
}

export default function ParsedDocPreview({
  kind,
  fileName,
  result,
  onReset,
}: {
  kind: "bill" | "eob";
  fileName: string;
  result: ParseDocumentResponse;
  onReset?: () => void;
}) {
  const { parsed, reconciliation, flags } = result;
  const pill = verdictPill(reconciliation);
  const balance = kind === "bill" ? parsed.patient_balance : parsed.patient_responsibility_total;
  const balanceLabel = kind === "bill" ? "Your balance" : "Patient responsibility";
  const cell: React.CSSProperties = { padding: "8px 0", borderTop: "1px solid var(--border)", fontSize: 14 };

  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div className="document-icon">📄</div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ fontWeight: 600 }}>{fileName}</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 2 }}>
            {parsed.line_items.length} line item{parsed.line_items.length === 1 ? "" : "s"} extracted ·{" "}
            {reconciliation.matches} verified against your case records
          </div>
        </div>
        <span className={`pill ${pill.cls}`}>{pill.label}</span>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 16 }}>
        <thead>
          <tr>
            {["CPT", "Description", "Date", "Billed"].map((h, i) => (
              <th
                key={h}
                style={{
                  textAlign: i === 3 ? "right" : "left",
                  fontSize: 12,
                  fontWeight: 500,
                  letterSpacing: "0.02em",
                  textTransform: "uppercase",
                  color: "var(--text-tertiary)",
                  padding: "0 0 8px",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {parsed.line_items.map((li, i) => (
            <tr key={`${li.cpt}-${i}`}>
              <td className="mono-figure" style={{ ...cell, fontSize: 13, paddingRight: 16 }}>{li.cpt}</td>
              <td style={{ ...cell, paddingRight: 16 }}>
                {li.description ?? "–"}
                {li.dx_codes && li.dx_codes.length > 0 && (
                  <span className="mono" style={{ fontSize: 11, color: "var(--text-tertiary)", marginLeft: 8 }}>
                    dx {li.dx_codes.join(", ")}
                  </span>
                )}
              </td>
              <td style={{ ...cell, color: "var(--text-secondary)", fontSize: 13, paddingRight: 16, whiteSpace: "nowrap" }}>
                {li.date_of_service ?? "–"}
              </td>
              <td className="mono-figure" style={{ ...cell, textAlign: "right", whiteSpace: "nowrap" }}>
                {money(li.billed_amount)}
              </td>
            </tr>
          ))}
          <tr>
            <td colSpan={3} style={{ ...cell, fontWeight: 600 }}>
              Total billed
            </td>
            <td className="mono-figure" style={{ ...cell, textAlign: "right", fontWeight: 600 }}>
              {money(parsed.total_billed)}
            </td>
          </tr>
          {balance != null && (
            <tr>
              <td colSpan={3} style={{ ...cell, fontWeight: 600 }}>
                {balanceLabel}
              </td>
              <td className="mono-figure" style={{ ...cell, textAlign: "right", fontWeight: 600 }}>
                {money(balance)}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {reconciliation.mismatches.length > 0 && (
        <div className="finding-card" style={{ marginTop: 16, marginBottom: 0 }}>
          <strong style={{ fontSize: 13 }}>Where this differs from your case records</strong>
          {reconciliation.mismatches.map((m, i) => (
            <div key={i} className="finding-evidence">
              <span className="cpt" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>CPT {m.cpt}</span>{" "}
              · {m.field.replaceAll("_", " ")}: parsed {fmtValue(m.parsed)} vs. expected {fmtValue(m.expected)}
            </div>
          ))}
        </div>
      )}

      {flags.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h3
            style={{
              fontSize: 13,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--text-tertiary)",
              marginBottom: 8,
              fontFamily: "var(--font-body)",
            }}
          >
            {flags.length} finding{flags.length === 1 ? "" : "s"} worth arguing
          </h3>
          {flags.map((flag, i) => (
            <div className="finding-card" key={i} style={{ marginBottom: 8 }}>
              <div className="finding-head">
                <div>
                  {flag.cpt && <span className="cpt">CPT {flag.cpt} · </span>}
                  <strong>{FLAG_LABELS[flag.type] ?? flag.type}</strong>
                </div>
                <span className="impact">+{money(flag.dollar_impact)}</span>
              </div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 6 }}>
                {evidenceLine(flag)}
              </div>
            </div>
          ))}
        </div>
      )}

      {onReset && (
        <button
          type="button"
          onClick={onReset}
          style={{
            background: "none",
            border: "none",
            color: "var(--text-tertiary)",
            fontSize: 13,
            marginTop: 12,
            cursor: "pointer",
            textDecoration: "underline",
            padding: 0,
          }}
        >
          Upload a different file
        </button>
      )}
    </div>
  );
}
