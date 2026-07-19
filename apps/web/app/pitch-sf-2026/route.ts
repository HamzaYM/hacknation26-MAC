import { readFile } from "node:fs/promises";
import path from "node:path";

// Serves the pitch deck at exactly /pitch-sf-2026 (no .html suffix).
// The deck is a fully self-contained HTML file with zero external network
// requests — fonts, anime.js and images are all vendored under /pitch-assets.
// We read it from disk PER REQUEST so edits show up without a dev restart,
// and we bypass the React RootLayout on purpose (that layout injects Google
// Fonts + Fontshare <link> tags, which would break the zero-external-request
// guarantee the venue wifi demands).
export const dynamic = "force-dynamic";

export async function GET() {
  const file = path.join(process.cwd(), "presentation", "pitch.html");
  const html = await readFile(file, "utf-8");
  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
