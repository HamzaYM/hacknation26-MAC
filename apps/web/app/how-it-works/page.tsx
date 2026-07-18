import Logo from "../../components/Logo";

// Stats are sourced from the team's Research.md brief — figures marked
// "directional" there (survey/advocacy-industry estimates) are labeled as
// such here too, not presented as settled fact. See Research.md and
// PRD.md §2 for full sourcing.
const STATS = [
  { value: "$220B", label: "in medical debt held by Americans today", source: "KFF, 2025" },
  { value: "3.4×", label: "average hospital markup over Medicare cost — up to 12.6× at outliers", source: "Bai & Anderson, Health Affairs 2015" },
  { value: "254%", label: "of Medicare rates, on average, paid by private insurers for the same care", source: "RAND Hospital Price Transparency Study, 2024" },
  { value: "49–80%", label: "of medical bills are estimated to contain errors", source: "advocacy-industry estimate, directional" },
];

const OUTCOME_STATS = [
  { value: "93%", label: "of people who negotiate their bill get it reduced", source: "LendingTree, 2021" },
  { value: "78%", label: "who dispute a charge get it reduced or removed", source: "AKASA/YouGov, 2022" },
  { value: "64%", label: "of Americans never even challenge a bill they suspect is wrong", source: "AKASA/YouGov, 2022" },
];

export default function HowItWorks() {
  return (
    <div className="marketing" style={{ minHeight: "auto", paddingBottom: 80 }}>
      <nav className="marketing-nav">
        <a href="/" style={{ textDecoration: "none", color: "inherit" }}>
          <Logo />
        </a>
        <div className="marketing-nav-links">
          <a href="/how-it-works">How it works</a>
          <a href="/how-it-works#pricing">Pricing</a>
          <a href="/login" className="btn btn-secondary" style={{ padding: "8px 20px" }}>
            Log in
          </a>
        </div>
      </nav>

      <section className="hiw-section">
        <h1 className="hiw-h1">The prices aren&apos;t fixed. Almost nobody asks.</h1>
        <p className="hiw-lede">
          Medical bills aren&apos;t like a restaurant check — the sticker price is closer to a
          suggestion. The numbers below are why.
        </p>

        <div className="hiw-stat-grid">
          {STATS.map((s) => (
            <div className="hiw-stat" key={s.label}>
              <div className="hiw-stat-value">{s.value}</div>
              <div className="hiw-stat-label">{s.label}</div>
              <div className="hiw-stat-source">{s.source}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="hiw-section hiw-section-alt">
        <h2 className="hiw-h2">Here&apos;s the part that should make you mad</h2>
        <p className="hiw-lede">Asking almost always works. Almost nobody asks.</p>
        <div className="hiw-stat-grid hiw-stat-grid-3">
          {OUTCOME_STATS.map((s) => (
            <div className="hiw-stat" key={s.label}>
              <div className="hiw-stat-value accent">{s.value}</div>
              <div className="hiw-stat-label">{s.label}</div>
              <div className="hiw-stat-source">{s.source}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="hiw-section">
        <h2 className="hiw-h2">How Haggl works</h2>
        <div className="hiw-steps">
          <div className="hiw-step">
            <div className="hiw-step-num">1</div>
            <h3>Upload your bill</h3>
            <p>
              A PDF or photo of your medical bill — and your EOB if you have it. We read both,
              cross-check them against Medicare rates and the hospital&apos;s own posted prices, and
              flag every error, overcharge, and legal protection working in your favor.
            </p>
          </div>
          <div className="hiw-step">
            <div className="hiw-step-num">2</div>
            <h3>We call</h3>
            <p>
              A real phone call to the billing office — disclosed as AI from the first thirty
              seconds, never bluffing, citing only numbers we can prove. We negotiate the way a
              good human advocate would: politely, persistently, and armed with your specific
              case.
            </p>
          </div>
          <div className="hiw-step">
            <div className="hiw-step-num">3</div>
            <h3>You save</h3>
            <p>
              Watch the balance move in real time. Cash in whenever you&apos;re satisfied, or let us
              keep pushing for more — every call, every dollar, and every reference number is
              logged for you to see.
            </p>
          </div>
        </div>
      </section>

      <section className="hiw-section hiw-section-alt" id="pricing">
        <h2 className="hiw-h2">Pricing</h2>
        <div className="hiw-pricing-card">
          <div className="hiw-pricing-figure">25%</div>
          <p className="hiw-pricing-detail">
            of what we save you — capped at <strong>$2,000</strong> per bill. Nothing upfront,
            nothing if we don&apos;t save you anything.
          </p>
          <ul className="hiw-pricing-list">
            <li>No savings, no fee — ever</li>
            <li>You see the exact math before you pay anything</li>
            <li>Cash in partial savings anytime; we only charge on what&apos;s actually confirmed</li>
          </ul>
        </div>
        <p style={{ fontSize: 13, color: "var(--text-tertiary)", maxWidth: 560, margin: "16px auto 0", textAlign: "center" }}>
          Higher than a document-only bill-review service, because we&apos;re doing more: real phone
          calls, not just a negotiation letter. Still well under what a human medical-bill advocate
          charges.
        </p>
      </section>
    </div>
  );
}
