"use client";

import { usePathname } from "next/navigation";
import Logo from "./Logo";
import { signOut, useSession } from "../lib/auth";

// Marketing, login, and War Room own their own full-bleed layout; every
// other route gets the internal product topbar/nav.
const BARE_ROUTES = ["/", "/login", "/warroom", "/how-it-works"];
const BARE_PREFIXES = ["/warroom"];

const NAV_ITEMS = [
  { href: "/bills", label: "Bills" },
  { href: "/action-items", label: "Action Items" },
  { href: "/voice", label: "Voice" },
  { href: "/profile", label: "Profile" },
  { href: "/warroom", label: "War Room" },
  { href: "/report", label: "Case file" },
];

export default function Chrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Session only decorates the chrome — deliberately no route guards, so
  // every screen keeps working logged-out (demo safety).
  const session = useSession();
  const bare = BARE_ROUTES.includes(pathname) || BARE_PREFIXES.some((p) => pathname.startsWith(p));

  if (bare) return <>{children}</>;

  const displayName =
    (session?.user?.user_metadata?.name as string | undefined) ?? session?.user?.email ?? "";


  return (
    <>
      <header className="topbar">
        <Logo />
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
          <nav className="nav-pills">
            {NAV_ITEMS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className={`nav-pill ${pathname.startsWith(item.href) ? "active" : ""}`}
              >
                {item.label}
              </a>
            ))}
          </nav>
          {session && (
            <span className="user-strip" style={{ padding: 0 }} title={session.user?.email ?? undefined}>
              <span className="avatar">{(displayName || "?").charAt(0).toUpperCase()}</span>
              <button
                type="button"
                onClick={() => signOut()}
                style={{
                  background: "none",
                  border: "none",
                  padding: 0,
                  fontFamily: "var(--font-body)",
                  fontSize: 14,
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                Log out
              </button>
            </span>
          )}
        </div>
      </header>
      <main>{children}</main>
    </>
  );
}
