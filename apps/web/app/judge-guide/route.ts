import { readFile } from "node:fs/promises";
import path from "node:path";

// Serves the judge-guide page at exactly /judge-guide (no .html suffix).
// Same rationale as /pitch-sf-2026 and /tech-video: the file is fully
// self-contained with zero external network requests (system fonts, inline SVG,
// base64 screenshots, no CDN), read from disk PER REQUEST so edits show up
// without a dev restart, and it bypasses the React RootLayout on purpose (that
// layout injects Google Fonts + Fontshare <link> tags, which would break the
// zero-external-request guarantee).
export const dynamic = "force-dynamic";

export async function GET() {
  const file = path.join(process.cwd(), "presentation", "judge-guide.html");
  const html = await readFile(file, "utf-8");
  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
