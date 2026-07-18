"use client";

import { useState } from "react";
import { supabase } from "../../lib/supabase";
import Logo from "../../components/Logo";

export default function Login() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  async function sendMagicLink(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setStatus("sending");
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: typeof window !== "undefined" ? `${window.location.origin}/onboard` : undefined },
    });
    setStatus(error ? "error" : "sent");
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <a href="/" style={{ display: "inline-block", marginBottom: 24, textDecoration: "none", color: "inherit" }}>
          <Logo />
        </a>

        {status === "sent" ? (
          <>
            <h1 style={{ fontSize: 22, marginBottom: 8 }}>Check your email</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 15, lineHeight: 1.6 }}>
              We sent a sign-in link to <strong>{email}</strong>. Click it to continue to your
              case.
            </p>
          </>
        ) : (
          <>
            <h1 style={{ fontSize: 22, marginBottom: 8 }}>Welcome back</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: 15, marginBottom: 24 }}>
              We&apos;ll email you a link — no password to remember.
            </p>

            <form onSubmit={sendMagicLink}>
              <input
                type="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <button type="submit" className="btn btn-primary" disabled={status === "sending"}>
                {status === "sending" ? "Sending…" : "Send magic link"}
              </button>
            </form>

            {status === "error" && (
              <p style={{ color: "var(--destructive)", fontSize: 13, marginTop: 12 }}>
                Something went wrong sending that link. Try again in a moment.
              </p>
            )}

            <div className="login-divider">or</div>

            <a href="/onboard" className="btn btn-secondary" style={{ textDecoration: "none" }}>
              Skip to demo →
            </a>
            <p style={{ color: "var(--text-tertiary)", fontSize: 12, marginTop: 24 }}>
              🔒 Bank-level encryption · you can revoke access anytime
            </p>
          </>
        )}
      </div>
    </div>
  );
}
