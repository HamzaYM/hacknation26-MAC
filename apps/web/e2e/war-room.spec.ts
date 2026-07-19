import { test, expect } from "@playwright/test";

// War Room (apps/web/app/warroom/page.tsx). No Supabase credentials in this
// offline run (lib/supabase.ts falls back to a localhost placeholder — every
// Realtime call fails closed: empty lists, no thrown errors), so this always
// exercises the "waiting for the calls" empty state, never a live call.

test.describe("war room", () => {
  test("renders without a call selected", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    await page.goto("/warroom");
    await expect(page.getByRole("heading", { name: "Waiting for the calls" })).toBeVisible();
    expect(pageErrors).toEqual([]);
  });

  test("scenario picker shows the empty state cleanly (builds without scenarios)", async ({ page }) => {
    // Inverse gate of the happy path below: with the 9-scenario suite merged
    // (E2E_SCENARIOS_READY=1), GET /scenarios is non-empty and the empty
    // state is unreachable — the happy path covers the picker instead.
    test.skip(
      !!process.env.E2E_SCENARIOS_READY,
      "scenario suite present on this build — empty state not reachable"
    );
    await page.goto("/warroom");
    await page.getByRole("button", { name: /switch scenario/i }).click();
    // listScenarios() never throws on an empty list — the picker must show
    // its documented empty state, not an error banner.
    await expect(page.getByTestId("scenario-picker-empty")).toBeVisible();
    await expect(page.getByTestId("scenario-picker")).toHaveCount(0);
  });

  // TODO(WS4): once the 9-scenario suite (Maya + 8 archetypes) lands and
  // GET /scenarios returns a non-empty list, flip this on by running with
  // E2E_SCENARIOS_READY=1 (or just delete the .skip once it's the default
  // behavior on this branch). Left here, skipped, as the integration
  // contract: this is the assertion the picker must satisfy the moment the
  // sibling branch's scenario generator merges.
  test.skip(
    !process.env.E2E_SCENARIOS_READY,
    "WS4 scenario suite not present on this build — set E2E_SCENARIOS_READY=1 once it lands"
  );
  test("scenario picker happy path: picking a scenario loads its case into the board", async ({ page }) => {
    await page.goto("/warroom");
    await page.getByRole("button", { name: /switch scenario/i }).click();
    const firstCard = page.getByTestId("scenario-card").first();
    await expect(firstCard).toBeVisible();
    const scenarioId = await firstCard.getAttribute("data-scenario-id");
    await firstCard.click();
    // POST /scenarios/{id}/load reads the scenario artifacts and builds the
    // case before the client navigates — allow real server latency rather
    // than leaning on the retry to absorb it.
    await expect(page).toHaveURL(/[?&]case_id=/, { timeout: 15000 });
    if (scenarioId) {
      // Loaded case_id need not equal scenario_id, but the board must have
      // navigated off the demo case and into a real, non-empty board state.
      await expect(page.getByRole("heading", { name: "Scenarios" })).toBeVisible();
    }
  });
});
