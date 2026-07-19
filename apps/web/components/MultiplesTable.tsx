import type { BenchmarkReport, LineBenchmark } from "../lib/types";
import { money } from "../lib/savings";
import CoverageBadge from "./CoverageBadge";
import EvidenceToggle from "./EvidenceToggle";

// Per-line multiples table (decision #10, dual framing): the headline $
// anchor/target band lives in the totals row; each line also gets its own
// "N.Nx Medicare" reading so a rep can't dismiss the ask as one cherry-picked
// number. Lines with rand_flag (billed > the config RAND ceiling, default
// 2.54x Medicare) get a clear overcharge treatment.
function medicareCell(li: LineBenchmark) {
  const medicareAnchor = li.anchors.find((a) => a.method === "medicare");
  if (!medicareAnchor) return "–";
  return money(medicareAnchor.value);
}

function multipleLabel(m?: number | null) {
  if (m == null) return "–";
  return `${m.toFixed(1)}×`;
}

export default function MultiplesTable({ report }: { report: BenchmarkReport }) {
  const { lines, totals } = report;
  const cell: React.CSSProperties = { padding: "8px 10px", borderTop: "1px solid var(--border)", fontSize: 13.5, verticalAlign: "top" };
  const head: React.CSSProperties = {
    textAlign: "left",
    fontSize: 11.5,
    fontWeight: 500,
    letterSpacing: "0.02em",
    textTransform: "uppercase",
    color: "var(--text-tertiary)",
    padding: "0 10px 8px",
    whiteSpace: "nowrap",
  };

  return (
    <div>
      <div style={{ overflowX: "auto" }}>
        <table data-testid="multiples-table" style={{ width: "100%", borderCollapse: "collapse", minWidth: 720 }}>
          <thead>
            <tr>
              <th style={head}>Code</th>
              <th style={head}>Description</th>
              <th style={{ ...head, textAlign: "right" }}>Billed</th>
              <th style={{ ...head, textAlign: "right" }}>Medicare</th>
              <th style={{ ...head, textAlign: "right" }}>× Medicare</th>
              <th style={{ ...head, textAlign: "right" }}>Fair band</th>
              <th style={{ ...head, textAlign: "right" }}>Excess</th>
              <th style={head}>Coverage</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((li, i) => {
              const overcharge = li.rand_flag;
              return (
                <tr key={`${li.code}-${i}`} style={overcharge ? { background: "var(--flag-tint)" } : undefined}>
                  <td className="mono-figure" style={{ ...cell, whiteSpace: "nowrap" }}>
                    {li.code}
                    <div style={{ fontSize: 10.5, color: "var(--text-tertiary)" }}>{li.code_type}</div>
                  </td>
                  <td style={cell}>
                    {li.description ?? "–"}
                    <EvidenceToggle anchors={li.anchors} />
                  </td>
                  <td className="mono-figure" style={{ ...cell, textAlign: "right", whiteSpace: "nowrap" }}>
                    {money(li.billed)}
                  </td>
                  <td className="mono-figure" style={{ ...cell, textAlign: "right", whiteSpace: "nowrap" }}>
                    {medicareCell(li)}
                  </td>
                  <td
                    className="mono-figure"
                    style={{
                      ...cell,
                      textAlign: "right",
                      whiteSpace: "nowrap",
                      fontWeight: overcharge ? 700 : 400,
                      color: overcharge ? "var(--destructive)" : "var(--text-primary)",
                    }}
                  >
                    {multipleLabel(li.medicare_multiple)}
                    {overcharge && (
                      <div style={{ fontSize: 10.5, fontWeight: 600, color: "var(--destructive)" }}>overcharge</div>
                    )}
                  </td>
                  <td className="mono-figure" style={{ ...cell, textAlign: "right", whiteSpace: "nowrap" }}>
                    {li.fair_band ? `${money(li.fair_band.low)}–${money(li.fair_band.high)}` : "–"}
                  </td>
                  <td
                    className="mono-figure"
                    style={{ ...cell, textAlign: "right", whiteSpace: "nowrap", color: li.excess_above_band > 0 ? "var(--flag)" : "var(--text-primary)" }}
                  >
                    {li.excess_above_band > 0 ? `+${money(li.excess_above_band)}` : "–"}
                  </td>
                  <td style={cell}>
                    <CoverageBadge coverage={li.coverage} />
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={2} style={{ ...cell, fontWeight: 700, borderTop: "2px solid var(--text-primary)" }}>
                Total
              </td>
              <td className="mono-figure" style={{ ...cell, textAlign: "right", fontWeight: 700, borderTop: "2px solid var(--text-primary)" }}>
                {money(totals.billed)}
              </td>
              <td className="mono-figure" style={{ ...cell, textAlign: "right", fontWeight: 700, borderTop: "2px solid var(--text-primary)" }}>
                {money(totals.medicare)}
              </td>
              <td className="mono-figure" style={{ ...cell, textAlign: "right", fontWeight: 700, borderTop: "2px solid var(--text-primary)" }}>
                {multipleLabel(totals.medicare_multiple)}
              </td>
              <td className="mono-figure" style={{ ...cell, textAlign: "right", fontWeight: 700, borderTop: "2px solid var(--text-primary)" }}>
                {money(totals.fair_band_low)}–{money(totals.fair_band_high)}
              </td>
              <td className="mono-figure" style={{ ...cell, textAlign: "right", fontWeight: 700, borderTop: "2px solid var(--text-primary)", color: "var(--flag)" }}>
                {totals.excess_above_band > 0 ? `+${money(totals.excess_above_band)}` : "–"}
              </td>
              <td style={{ ...cell, borderTop: "2px solid var(--text-primary)" }} />
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="stat-pair" style={{ marginTop: 16 }}>
        <div className="stat">
          <div className="stat-num accent mono-figure">{money(totals.ask_anchor)}</div>
          <div className="stat-cap">Opening ask</div>
        </div>
        <div className="stat">
          <div className="stat-num mono-figure">{money(totals.ask_target)}</div>
          <div className="stat-cap">Target</div>
        </div>
        <div className="stat">
          <div className="stat-num mono-figure">{money(totals.floor)}</div>
          <div className="stat-cap">Floor · never asks below this</div>
        </div>
      </div>
    </div>
  );
}
