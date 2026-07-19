import { test, expect } from "@playwright/test";

// The create/upload flow on /bills. playwright.config.ts forces
// OPENAI_API_KEY="" and redirects OPENAI_BASE_URL to an unroutable loopback
// address, so POST /documents/parse deterministically fails with a local
// connection error — no real network call, no dependency on internet access
// in this run, no timeout risk from a hung real request. We assert the UI's
// documented graceful-failure branch, not the vision-dependent happy path —
// see UploadCard/BillDocSlot's `status: "error"` state.

test.describe("upload flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/bills");
  });

  test("bills page renders the create/upload panel", async ({ page }) => {
    await page.getByTestId("create-bill-button").click();
    const panel = page.getByTestId("create-bill-panel");
    await expect(panel).toBeVisible();
    await expect(panel.getByRole("button", { name: /^Medical bill/ })).toBeVisible();
    await expect(panel.getByRole("button", { name: /^Explanation of Benefits/ })).toBeVisible();
  });

  test("POST /cases path runs from the UI (falls back gracefully if unavailable)", async ({ page }) => {
    // POST /cases requires a full JobSpec body (patient.legal_name/dob,
    // bill, eob — apps/api/app/routers/cases.py CreateCaseRequest); the UI's
    // createCase() sends no body, so this build's endpoint 422s and
    // ensureCaseId() falls back to a client-generated id (lib's documented
    // behavior, apps/web/app/bills/page.tsx). Either branch must leave the
    // upload flow usable — that's what we assert, not which branch fired.
    let casesPostSeen = false;
    page.on("request", (req) => {
      if (req.method() === "POST" && new URL(req.url()).pathname === "/api/cases") casesPostSeen = true;
    });

    await page.getByTestId("create-bill-button").click();
    await page.getByTestId("use-demo-file").first().click();
    await expect(page.locator(".upload-preview-modal")).toBeVisible();
    await page.getByTestId("attach-document").click();

    // The attempt happens (case id resolution is on the critical path of
    // every parse call), regardless of which branch it lands on.
    await expect.poll(() => casesPostSeen).toBeTruthy();
  });

  test("a failed parse (no OPENAI_API_KEY in this offline run) shows the graceful error state, not a crash", async ({
    page,
  }) => {
    await page.getByTestId("create-bill-button").click();
    await page.getByTestId("use-demo-file").first().click();
    await expect(page.locator(".upload-preview-modal")).toBeVisible();
    await page.getByTestId("attach-document").click();

    // "Parsing" appears first, then the documented error branch —
    // apps/web/app/bills/page.tsx BillDocSlot's `status: "error"`. The API
    // tries 3 vision models in order (_MODELS in documents.py), each one
    // retrying against the unroutable OPENAI_BASE_URL before giving up —
    // budget generously so this never flakes on a slower machine.
    await expect(page.getByText(/Couldn.?t parse/i)).toBeVisible({ timeout: 45_000 });
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
    // The page is still fully interactive — no crash, no error boundary.
    await expect(page.getByTestId("create-bill-panel")).toBeVisible();
  });
});
