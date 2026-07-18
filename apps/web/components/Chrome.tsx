"use client";

import { usePathname } from "next/navigation";
import Logo from "./Logo";

// Marketing, login, and War Room own their own full-bleed layout; every
// other route gets the internal product topbar/nav.
const BARE_ROUTES = ["/", "/login", "/warroom"];
const BARE_PREFIXES = ["/warroom"];

const NAV_ITEMS = [
  { href: "/bills", label: "Bills" },
  { href: "/action-items", label: "Action Items" },
  { href: "/profile", label: "Profile" },
  { href: "/warroom", label: "War Room" },
];

export default function Chrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const bare = BARE_ROUTES.includes(pathname) || BARE_PREFIXES.some((p) => pathname.startsWith(p));

  if (bare) return <>{children}</>;

  return (
    <>
      <header className="topbar">
        <Logo />
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
      </header>
      <main>{children}</main>
    </>
  );
}
