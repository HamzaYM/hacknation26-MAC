"""Repeatable, READ-ONLY product screenshots for the judge user-guide PDF.

Drives the running web app with Playwright (shared venv) and captures one
screenshot per walkthrough step into deck/guide-assets/. Re-run this after the
UI-cleanup PRs merge to refresh every shot, then rebuild the PDF from
deck/judge-guide.html.

READ-ONLY BY DESIGN - this script only navigates and screenshots. It never
launches calls, never uploads a document, and never confirms/mutates Maya's
case. The single write is the auth session created by logging in.

Usage (from the repo root, with the shared venv active):
    python scripts/capture_guide_shots.py

Env overrides (all optional):
    GUIDE_BASE_URL   default http://127.0.0.1:3000
    GUIDE_EMAIL      default maya@hagglfor.me
    GUIDE_PASSWORD   default HagglDemo2026!

Requires the web app already running on GUIDE_BASE_URL. This script does not
start, restart, or bind any server.
"""
from __future__ import annotations

import os
import pathlib

from playwright.sync_api import sync_playwright

BASE = os.environ.get("GUIDE_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
EMAIL = os.environ.get("GUIDE_EMAIL", "maya@hagglfor.me")
PASSWORD = os.environ.get("GUIDE_PASSWORD", "HagglDemo2026!")

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "deck" / "guide-assets"
# Maya's flagship case (DEMO_CASE_ID) - the diagnosis-view fallback if the
# bills page doesn't yield an entity-card href for the logged-in user.
DEMO_CASE_ID = "00000000-0000-0000-0000-000000000001"
VIEWPORT = {"width": 1280, "height": 800}


def settle(page, selector: str | None = None, ms: int = 1400) -> None:
    """Wait for the network to go quiet, an optional key element, then a beat
    for data fetches / entrance animations to finish before the shot."""
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    if selector:
        try:
            page.wait_for_selector(selector, timeout=8000)
        except Exception:
            pass
    page.wait_for_timeout(ms)


def shot(page, name: str) -> None:
    path = OUT / name
    page.screenshot(path=str(path), full_page=False)
    print(f"  captured {name}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Capturing guide shots from {BASE} → {OUT}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = ctx.new_page()

        # 1 - landing page
        page.goto(f"{BASE}/", wait_until="domcontentloaded")
        settle(page)
        shot(page, "01-landing.png")

        # 2 - login (show the filled form, then sign in)
        page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        settle(page, "input[type=email]")
        try:
            page.fill("input[type=email]", EMAIL)
            page.fill("input[type=password]", PASSWORD)
        except Exception as e:  # noqa: BLE001
            print(f"  (login form fill skipped: {e})")
        page.wait_for_timeout(400)
        shot(page, "02-login.png")

        # submit - establishes the session for the authed shots. If auth is
        # unavailable, the app falls back to Maya's case logged-out, so every
        # later shot still renders her data.
        try:
            page.click("button[type=submit]")
            page.wait_for_url("**/bills", timeout=15000)
        except Exception as e:  # noqa: BLE001
            print(f"  (login did not reach /bills, continuing logged-out: {e})")
            page.goto(f"{BASE}/bills", wait_until="domcontentloaded")

        # 3 - bills home
        settle(page, ".savings-hero")
        shot(page, "03-bills-home.png")

        # 4 - diagnosis view for Maya's bill (the 4 findings + flagged total).
        # Prefer the real entity-card link for whoever is logged in; fall back
        # to the flagship demo case id.
        href = None
        try:
            el = page.query_selector("a.entity-card")
            href = el.get_attribute("href") if el else None
        except Exception:  # noqa: BLE001
            href = None
        target = f"{BASE}{href}" if href else f"{BASE}/bills/{DEMO_CASE_ID}"
        page.goto(target, wait_until="domcontentloaded")
        settle(page, ms=1800)
        shot(page, "04-diagnosis.png")

        # 5 - the confirm gate ("Looks right, make the calls"). SCREENSHOT ONLY;
        # the launch button is never clicked.
        page.goto(f"{BASE}/confirm", wait_until="domcontentloaded")
        settle(page, ms=1800)
        shot(page, "05-confirm.png")

        # 6 - the live War Room
        page.goto(f"{BASE}/warroom", wait_until="domcontentloaded")
        settle(page, ms=2000)
        shot(page, "06-warroom.png")

        # 7 - the case file at /report (archived real calls with audio)
        page.goto(f"{BASE}/report", wait_until="domcontentloaded")
        settle(page, ms=2000)
        shot(page, "07-report.png")

        ctx.close()
        browser.close()
    print("done - screenshots in deck/guide-assets/")


if __name__ == "__main__":
    main()
