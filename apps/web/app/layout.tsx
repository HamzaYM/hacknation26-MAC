import type { Metadata } from "next";
import Chrome from "../components/Chrome";
import "./globals.css";

export const metadata: Metadata = {
  title: "Haggl — your medical bill just met its match",
  description: "An AI advocate that reads your hospital bill and talks the price down on a live call.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600..800&family=IBM+Plex+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <link href="https://api.fontshare.com/v2/css?f[]=general-sans@400,500,600,700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <Chrome>{children}</Chrome>
      </body>
    </html>
  );
}
