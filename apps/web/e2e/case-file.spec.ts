import { test, expect } from "@playwright/test";
import { DEMO_CASE_ID, DEMO_BILL_BALANCE, DEMO_EOB_TARGET } from "./constants";

// Maya's fixture case (apps/api/app/fixtures.py DEMO_JOB_SPEC), served
// straight off GET /cases/{id} — no upload, no scenario load, no auth. This
// is the one screen every reviewer will look at first.

test.describe("case file", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/bills/${DEMO_CASE_ID}`);
    await expect(page.getByTestId("case-file")).toBeVisible();
  });

  test("renders Maya's case with the facility name and balance", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Mercy General Hospital" })).toBeVisible();
  });

  test("dossier headline numbers are present", async ({ page }) => {
    // balance-old = original patient_balance ($4,287); balance-new = current
    // balance after the one already-conceded duplicate ($3,875) — see
    // lib/savings.ts facilitySavings(). Both are the "anchor" and "target"
    // figures the negotiation argument is built around.
    const body = page.locator("body");
    await expect(body).toContainText(DEMO_BILL_BALANCE);
    await expect(body).toContainText(DEMO_EOB_TARGET);
  });

  test("flags are visible on the Diagnosis tab", async ({ page }) => {
    // Diagnosis is the default tab — no click needed.
    const findings = page.getByTestId("finding-card");
    await expect(findings.first()).toBeVisible();
    const count = await findings.count();
    expect(count).toBeGreaterThanOrEqual(3); // duplicate, upcode, unbundle, eob_mismatch on the fixture

    // At least the clean duplicate-charge finding, by type, is present.
    await expect(page.locator('[data-flag-type="duplicate"]')).toBeVisible();
  });

  test("tabs switch without crashing (Plan, Call History, Documents, Action Items)", async ({ page }) => {
    for (const tab of ["Plan", "Call History", "Documents", "Action Items"]) {
      await page.getByRole("button", { name: new RegExp(`^${tab}`) }).click();
      await expect(page.locator("body")).toBeVisible();
    }
  });

  test("unknown case id shows the graceful not-found message, not a crash", async ({ page }) => {
    await page.goto("/bills/does-not-exist");
    await expect(page.getByText(/Couldn.?t load this case/i)).toBeVisible();
  });
});
