#!/usr/bin/env python3
"""WS6a — standalone E2E stack runner.

Boots the API (fixture/offline mode) and the web app together, exactly the
way playwright.config.ts's `webServer` array does, so a human can bring the
same hermetic stack up for manual poking without going through Playwright at
all: `python scripts/e2e_stack.py`, then open http://localhost:3000.

This is NOT invoked by `npx playwright test` (Playwright manages its own
child processes via the config's webServer array) — this script is the
"equivalent stack-runner" for everyone else: manual QA, screenshotting,
debugging a flaky spec by watching the browser instead of a trace file.

Zero external services: BENCHMARK_SOURCE=fixture, OPENAI_API_KEY forced empty
(a copied .env's key can never leak in — python-dotenv never overrides an
already-set env var, even an empty one), SUPABASE_DB_URL forced empty.
Ctrl+C tears both processes down.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"
WEB_DIR = REPO_ROOT / "apps" / "web"

API_URL = "http://localhost:8000/health"
WEB_URL = "http://localhost:3000"


def _url_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:  # nosec B310 - localhost only
            return 200 <= resp.status < 400
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False


def _wait_for(name: str, url: str, proc: subprocess.Popen, timeout_s: int = 60) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"{name} exited early with code {proc.returncode} before becoming healthy")
        if _url_ok(url):
            print(f"[e2e_stack] {name} healthy at {url}")
            return
        time.sleep(0.5)
    raise TimeoutError(f"{name} did not become healthy at {url} within {timeout_s}s")


def main() -> int:
    if not API_DIR.exists() or not WEB_DIR.exists():
        print("[e2e_stack] expected apps/api and apps/web next to this repo root", file=sys.stderr)
        return 1

    api_env = {
        **os.environ,
        "BENCHMARK_SOURCE": "fixture",
        "OPENAI_API_KEY": "",  # never dial with a real key
        # A bare empty key still lets openai.OpenAI() construct fine and dial
        # out for real (it only raises at construction when the key is
        # unset/None, not ""). Redirecting the base URL to an unroutable
        # loopback address is what actually keeps this offline: the vision
        # parse path fails fast with a local connection error instead of a
        # real (or hung, if genuinely offline) call to api.openai.com.
        "OPENAI_BASE_URL": "http://127.0.0.1:1/v1",
        "SUPABASE_DB_URL": "",  # hermetic: fixture-only persistence
        "PYTHONUNBUFFERED": "1",
    }
    web_env = {
        **os.environ,
        "NEXT_PUBLIC_SUPABASE_URL": os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "http://localhost:54321"),
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon-key-not-set"),
    }

    # Windows-safe: `uvicorn` as a python module (not the console-script shim)
    # and `npm.cmd`-resolving shell=True on Windows for the next dev server —
    # see e2e/README.md for why a bare `npm` Popen call fails on Windows.
    uvicorn_cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"]
    npm_cmd = "npm run dev" if os.name != "nt" else "npm run dev"

    print("[e2e_stack] starting API (uvicorn, BENCHMARK_SOURCE=fixture, no OPENAI key, no Supabase)…")
    api_proc = subprocess.Popen(uvicorn_cmd, cwd=API_DIR, env=api_env)

    print("[e2e_stack] starting web (next dev)…")
    web_proc = subprocess.Popen(npm_cmd, cwd=WEB_DIR, env=web_env, shell=(os.name == "nt"))

    procs = [("API", api_proc), ("web", web_proc)]

    def _shutdown(*_args) -> None:
        print("\n[e2e_stack] shutting down…")
        for name, proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for name, proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    try:
        _wait_for("API", API_URL, api_proc)
        _wait_for("web", WEB_URL, web_proc)
    except (TimeoutError, RuntimeError) as err:
        print(f"[e2e_stack] {err}", file=sys.stderr)
        _shutdown()
        return 1

    print("\n[e2e_stack] stack is up:")
    print(f"  API  -> {API_URL.rsplit('/', 1)[0]}")
    print(f"  web  -> {WEB_URL}")
    print("  Ctrl+C to stop both.\n")

    while True:
        for name, proc in procs:
            code = proc.poll()
            if code is not None:
                print(f"[e2e_stack] {name} exited with code {code}", file=sys.stderr)
                _shutdown()
                return 1
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
