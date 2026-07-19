"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithPassword } from "../../lib/auth";
import Logo from "../../components/Logo";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function logIn(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) return;
    setSubmitting(true);
    setError(null);
    const message = await signInWithPassword(email, password);
    if (message) {
      setSubmitting(false);
      setError(message);
      return;
    }
    router.push("/bills");
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <a href="/" style={{ display: "inline-block", marginBottom: 24, textDecoration: "none", color: "inherit" }}>
          <Logo />
        </a>

        <h1 style={{ fontSize: 22, marginBottom: 8 }}>Welcome back</h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 15, marginBottom: 24 }}>
          Log in to pick up where your negotiations left off.
        </p>

        <form onSubmit={logIn}>
          <input
            type="email"
            required
            placeholder="you@example.com"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            // A password-manager extension injects data-* attributes before
            // hydration; suppress the resulting attribute-mismatch warning.
            suppressHydrationWarning
          />
          <input
            type="password"
            required
            placeholder="Password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            suppressHydrationWarning
          />
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Logging in…" : "Log in"}
          </button>
        </form>

        {error && (
          <p style={{ color: "var(--destructive)", fontSize: 13, marginTop: 12 }}>{error}</p>
        )}

        <div className="login-divider">or</div>

        <a href="/onboard" className="btn btn-secondary" style={{ textDecoration: "none" }}>
          Skip to demo →
        </a>
        <p style={{ color: "var(--text-tertiary)", fontSize: 12, marginTop: 24 }}>
          🔒 Encrypted in transit and at rest · revoke access anytime
        </p>
      </div>
    </div>
  );
}
