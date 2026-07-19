import { test, expect } from "@playwright/test";

// Boots and home page render, entirely offline: BENCHMARK_SOURCE=fixture on
// the API (playwright.config.ts webServer), no Supabase/OpenAI credentials
// needed. This is the gate's smoke test — if this fails, nothing else will
// tell you anything useful.

test.describe("health", () => {
  test("API /health responds ok", async ({ request }) => {
    const res = await request.get("/api/health");
    expect(res.ok()).toBeTruthy();
    expect(await res.json()).toEqual({ ok: true });
  });

  test("home page renders with no console errors", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    // Network failures (e.g. the Google Fonts / Fontshare <link> tags in
    // layout.tsx, unreachable in an offline test run) surface as failed
    // requests, not console errors — they don't belong in this assertion,
    // and a flaky CDN must never fail this gate.
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByText(/just met its/i)).toBeVisible();

    expect(pageErrors, `uncaught page errors: ${pageErrors.join("; ")}`).toEqual([]);
    expect(consoleErrors, `console.error calls: ${consoleErrors.join("; ")}`).toEqual([]);
  });

  test("nav gets to Bills without crashing", async ({ page }) => {
    await page.goto("/how-it-works");
    await expect(page.locator("body")).toBeVisible();
  });
});
