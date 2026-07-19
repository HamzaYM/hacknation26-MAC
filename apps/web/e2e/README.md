# WS6a — Playwright E2E harness

The end-to-end gate: boots the real API (offline/fixture mode) and the real
web app together, then drives them with a headless browser. No Supabase, no
OpenAI, no ElevenLabs, no network — everything here is hermetic and
deterministic.

## Running

From `apps/web`:

```bash
npm install                 # first time only, or after a clean worktree
npx playwright install chromium   # first time only
npm run e2e                 # headless, CI-style
npm run e2e:ui              # interactive UI mode (great for debugging)
```

`npx playwright test` (equivalently `npm run e2e`) boots both servers itself
via `playwright.config.ts`'s `webServer` array — you don't need to start
uvicorn or `next dev` by hand. It waits on `GET :8000/health` and `GET
:3000/` before running any spec, and tears both processes down when the run
ends.

To bring the same stack up **without** Playwright — for manual poking,
screenshots, or watching the actual browser instead of a trace file — run:

```bash
python scripts/e2e_stack.py
```

from the repo root. Ctrl+C stops both processes. This is the "equivalent
stack-runner" mentioned in the WS6a brief; it is not invoked by the Playwright
run itself (Playwright manages its own child processes).

## Why hermetic

- `BENCHMARK_SOURCE=fixture` on the API — the sqlite/Supabase-backed
  chargemaster lookups are never touched.
- `OPENAI_API_KEY` is force-set to `""` for the API's `webServer` entry. This
  matters even if you have a real key sitting in `apps/api/.env` (per the
  workstream's "copy `.env` for optional live checks" convention):
  `python-dotenv`'s `load_dotenv()` never overrides an **already-set**
  environment variable, even an empty string, so the explicit `""` always
  wins. `openai.OpenAI()` raises immediately at client construction when the
  key is empty/missing (apps/api/app/routers/documents.py) — no network call,
  no timeout risk, a fast deterministic failure every run.
- `SUPABASE_DB_URL` is force-set to `""` — the API's persistence layer
  (`app/db.py`) already no-ops without it ("fixture-only mode"); the web
  app's Supabase client (`lib/supabase.ts`) falls back to an unreachable
  `localhost:54321` placeholder and every Realtime/auth call fails closed
  (empty lists, no session — never a thrown error).
- Screenshots/video are off by default (`use: { screenshot: "off", video:
  "off" }`); `trace: "on-first-retry"` only captures on the retry pass, so a
  green run produces no artifacts.

## Windows quirks

- **`python` on PATH, not `python3`.** `playwright.config.ts` shells out to
  `python -m uvicorn …` directly (not the `uvicorn` console-script shim) —
  more reliable across venvs/python launchers on Windows. If your `python`
  resolves to something without `uvicorn` installed, `pip install -r
  apps/api/requirements.txt` first.
- **Port cleanup.** If a previous run's `webServer` process didn't exit
  cleanly (killed test runner, crashed terminal), `:8000`/`:3000` can be left
  bound. Find and clear them:
  ```powershell
  Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
  Stop-Process -Id <pid> -Force
  # repeat for -LocalPort 3000
  ```
  `reuseExistingServer: !process.env.CI` means a *healthy* leftover server on
  either port is reused rather than treated as a conflict — only a
  half-dead one needs manual cleanup.
- **`npm.cmd` vs `npm`.** `scripts/e2e_stack.py` spawns the web dev server
  with `shell=True` on Windows specifically because a bare `Popen(["npm",
  ...])` fails to resolve `npm` (it's `npm.cmd`, a shell-resolved shim, not a
  directly-executable binary) on this platform. Playwright's own `webServer`
  command strings don't have this problem — they're always shell-interpreted.
- **git-bash vs PowerShell.** Both work for `npm run e2e`; the commands above
  are shown as plain shell since they're identical either way. No `sh`-only
  syntax is used anywhere in this harness.

## What's covered

- `health.spec.ts` — API `/health`, home page renders with zero console
  errors / uncaught page errors.
- `case-file.spec.ts` — `/bills/<DEMO_CASE_ID>` (Maya's fixture case):
  facility name, the two dossier headline numbers ($4,287 original balance /
  $3,875 current balance after the conceded duplicate), flags visible on the
  Diagnosis tab, tab switching, and the graceful not-found path for an
  unknown case id.
- `upload.spec.ts` — the create/upload panel renders; the demo-file → preview
  → attach path fires `POST /cases` (asserted as *attempted*, not as
  succeeding — this build's endpoint needs a full JobSpec body the UI
  intentionally doesn't send yet, so it 422s and the UI falls back to a
  client-generated case id, its documented behavior); a failed parse (no
  OpenAI key) lands on the UI's own graceful error state, not a crash.
- `war-room.spec.ts` — renders with no call selected; the scenario picker's
  empty state (no scenarios published on this build); a **skipped** happy-path
  spec for picking a scenario, gated behind `E2E_SCENARIOS_READY=1` — flip
  that env var (or delete the `.skip`) once WS4's 9-scenario suite lands.
- `evidence.spec.ts` — the multiples table + evidence toggle. `GET
  /cases/{id}/benchmark_report` has no route on this integration build yet
  (a sibling-worktree deliverable per `lib/api.ts`'s own comments), so these
  specs mock the endpoint with a schema-shaped fixture
  (`e2e/fixtures/benchmark-report.json`) to verify the UI contract
  deterministically today: the table renders, "Show evidence" is closed by
  default and reveals provenance (source/formula/confidence) on click, and
  any `estimated`-confidence anchor visibly says "estimated" — the
  discipline requirement. A separate spec in the same file asserts today's
  *real*, unmocked behavior: no multiples table, no crash, when the endpoint
  is genuinely unavailable.

## Adding `data-testid`s

Kept minimal and additive — only where a stable selector genuinely needed one
(a role/text selector wasn't good enough, e.g. two structurally-identical
upload slots). See `create-bill-button`, `create-bill-panel`,
`use-demo-file`, `attach-document`, `view-parsed-bill`, `scenario-picker` /
`scenario-picker-empty` / `scenario-card`, `evidence-toggle` /
`evidence-panel` / `evidence-anchor` (+ `data-confidence`), `multiples-table`,
`case-file`, `finding-card` (+ `data-flag-type`).
