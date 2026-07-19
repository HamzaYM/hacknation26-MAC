import MoneyRain from "../components/MoneyRain";
import Logo from "../components/Logo";
import { FEE_LINE } from "../lib/fees";

export default function Home() {
  return (
    <div className="marketing">
      <MoneyRain />

      <nav className="marketing-nav">
        <Logo />
        <div className="marketing-nav-links">
          <a href="/how-it-works">How it works</a>
          <a href="/how-it-works#pricing">Pricing</a>
          <a href="/login" className="btn btn-secondary" style={{ padding: "8px 20px" }}>
            Log in
          </a>
        </div>
      </nav>

      <section className="marketing-hero">
        <span className="badge-live">
          <span className="dot" />
          AI voice agents · live now
        </span>

        <h1 className="marketing-headline">
          your medical bill
          <br />
          just met its <span className="accent">match</span>
        </h1>

        <p className="marketing-sub">
          upload it, we call the billing dept and haggle it down while you touch grass. no calls,
          no hold music, no PhD in insurance.
        </p>

        <div className="marketing-cta-row" style={{ marginBottom: "var(--space-md)" }}>
          <a href="/login" className="btn btn-primary">
            Start saving, it&apos;s free →
          </a>
          <a href="/how-it-works" className="link-cta">
            see how it works
          </a>
        </div>

        <p
          style={{
            fontSize: 14,
            color: "var(--text-secondary)",
            maxWidth: 480,
            margin: "0 auto var(--space-2xl)",
          }}
        >
          {FEE_LINE}
        </p>

        <div className="stat-row">
          <div>
            <div className="stat-value">3 min</div>
            <div className="stat-label">to upload &amp; go</div>
          </div>
          <div className="stat-div" />
          <div>
            <div className="stat-value">$0</div>
            <div className="stat-label">until you save</div>
          </div>
        </div>
      </section>
    </div>
  );
}
