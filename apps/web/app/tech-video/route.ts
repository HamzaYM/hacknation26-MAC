import { readFile } from "node:fs/promises";
import path from "node:path";

// Serves the 60-second tech-video deck at exactly /tech-video (no .html suffix).
// Same rationale as /pitch-sf-2026: the file is self-contained (fonts vendored
// under /pitch-assets), read from disk per request so edits show up without a
// dev restart, and it bypasses the React RootLayout to keep the
// zero-external-request guarantee.
export const dynamic = "force-dynamic";

export async function GET() {
  const file = path.join(process.cwd(), "presentation", "tech-video.html");
  const html = await readFile(file, "utf-8");
  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
