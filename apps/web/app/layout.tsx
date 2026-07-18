import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Negotiator",
  description: "An AI advocate that reads your hospital bill and talks the price down on a live call.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <span className="brand">The Negotiator</span>
          <nav>
            <a href="/onboard">Onboard</a> · <a href="/intake">Intake</a> ·{" "}
            <a href="/confirm">Confirm</a> · <a href="/warroom">War Room</a> ·{" "}
            <a href="/report">Report</a>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
