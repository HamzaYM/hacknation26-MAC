import { test, expect } from "@playwright/test";
import benchmarkReport from "./fixtures/benchmark-report.json";
import { DEMO_CASE_ID } from "./constants";

// GET /cases/{id}/benchmark_report (the multiples table + evidence toggle's
// data source, contracts/anchor_set.schema.json) has no route registered in
// this integration build yet — apps/api/app/routers/cases.py only exposes
// job_spec/flags/action_plan/report; benchmark_report is a sibling-worktree
// (WS2/WS3) deliverable per apps/web/lib/api.ts's own comments. getBenchmarkReport()
// is written to degrade to null on any non-ok response, so the case page
// renders fine without it (see the "degrades gracefully" spec below) — but
// that also means the multiples table/evidence toggle have nothing to render
// against on THIS build's demo case.
//
// Rather than skip the deliverable outright, we intercept the route with a
// realistic BenchmarkReport payload (schema-shaped, built from the fixture
// case's own CPTs) so the UI contract — multiples table renders, evidence
// toggle reveals provenance, "estimated" anchors are labeled as such — is
// verified deterministically today. Delete the page.route mock once the real
// endpoint lands; the assertions underneath it should keep passing unchanged.

test.describe("evidence toggle + multiples table", () => {
  test.beforeEach(async ({ page }) => {
    await page.route(`**/api/cases/${DEMO_CASE_ID}/benchmark_report`, (route) =>
      route.fulfill({ json: benchmarkReport })
    );
    await page.goto(`/bills/${DEMO_CASE_ID}`);
    await expect(page.getByTestId("case-file")).toBeVisible();
  });

  test("multiples table renders per-line benchmarks", async ({ page }) => {
    const table = page.getByTestId("multiples-table");
    await expect(table).toBeVisible();
    await expect(table.getByText("99285")).toBeVisible();
    await expect(table.getByText("71046")).toBeVisible();
  });

  test("evidence toggle is hidden by default and reveals provenance on click", async ({ page }) => {
    const toggle = page.getByTestId("evidence-toggle").first();
    await expect(page.getByTestId("evidence-panel")).toHaveCount(0);
    await toggle.click();
    const panel = page.getByTestId("evidence-panel").first();
    await expect(panel).toBeVisible();
    await expect(panel.getByText(/confidence/).first()).toBeVisible();
    await expect(panel.getByText(/source:/).first()).toBeVisible();
  });

  test("estimated-label discipline: any 'estimated' anchor shows its label", async ({ page }) => {
    // Open every evidence toggle on the page.
    const toggles = page.getByTestId("evidence-toggle");
    const n = await toggles.count();
    for (let i = 0; i < n; i++) await toggles.nth(i).click();

    const estimatedRows = page.locator('[data-testid="evidence-anchor"][data-confidence="estimated"]');
    await expect(estimatedRows).toHaveCount(1); // the 99285 RAND-norm anchor in the fixture
    await expect(estimatedRows.first()).toContainText("estimated");
    await expect(estimatedRows.first().getByText(/estimated \(RAND norm\)/)).toBeVisible();
  });
});

test.describe("diagnosis tab degrades gracefully without benchmark_report", () => {
  test("no multiples table, no crash, when the endpoint is unavailable (this build's real behavior)", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    await page.goto(`/bills/${DEMO_CASE_ID}`);
    await expect(page.getByTestId("case-file")).toBeVisible();
    await expect(page.getByTestId("finding-card").first()).toBeVisible();
    await expect(page.getByTestId("multiples-table")).toHaveCount(0);
    expect(pageErrors).toEqual([]);
  });
});
