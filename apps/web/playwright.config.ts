import path from "path";
import { defineConfig, devices } from "@playwright/test";

// WS6a — E2E gate. Boots BOTH the API (fixture/offline mode, no external
// services) and the web app, entirely hermetic: no Supabase, no live
// OpenAI/ElevenLabs calls, no network dependency. See e2e/README.md for the
// Windows-specific notes (port cleanup, uvicorn spawn, `python` vs `python3`).
const apiDir = path.resolve(__dirname, "../api");

// OPENAI_API_KEY is force-set to "" and OPENAI_BASE_URL redirected to an
// unroutable loopback address so a real key/network access that happens to
// be available (a copied apps/api/.env, ambient internet in CI) can NEVER
// leak into this run — python-dotenv's load_dotenv() never overrides an
// already-set env var, so these explicit values always win over the .env
// file. The openai SDK only raises at client-construction time when the key
// is exactly `None` (unset), not `""` (see openai._client.OpenAI.__init__) —
// an empty string still dials out — so redirecting OPENAI_BASE_URL is what
// actually keeps this hermetic: the request fails fast with a local
// connection error instead of a real (or hung, if truly offline) network
// call to api.openai.com. That keeps the vision-parse path deterministically
// on its graceful-failure branch, with zero dependency on internet access.
const API_ENV: Record<string, string> = {
  BENCHMARK_SOURCE: "fixture",
  OPENAI_API_KEY: "",
  OPENAI_BASE_URL: "http://127.0.0.1:1/v1",
  SUPABASE_DB_URL: "",
  PYTHONUNBUFFERED: "1",
};

// The web app talks to Supabase (auth + Realtime) for session state and the
// War Room live feeds. Without real credentials it falls back to a localhost
// placeholder (lib/supabase.ts) and every call fails closed — no session,
// empty call lists — never a thrown console error. That's the deterministic,
// hermetic behavior these specs assert against.
const WEB_ENV: Record<string, string> = {
  NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://localhost:54321",
  NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "anon-key-not-set",
};

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 1,
  workers: process.env.CI ? 2 : undefined,
  reporter: [["list"], ["html", { open: "never", outputFolder: "e2e/report" }]],
  outputDir: "e2e/test-results",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "off",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // Two independent processes, booted in parallel, each gated on its own
  // health check. reuseExistingServer keeps local iteration fast (a server
  // you already have running on :8000/:3000 is left alone outside CI); CI
  // always starts fresh.
  webServer: [
    {
      command: "python -m uvicorn app.main:app --port 8000",
      cwd: apiDir,
      url: "http://localhost:8000/health",
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
      env: API_ENV,
    },
    {
      command: "npm run dev",
      cwd: __dirname,
      url: "http://localhost:3000",
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
      env: WEB_ENV,
    },
  ],
});
