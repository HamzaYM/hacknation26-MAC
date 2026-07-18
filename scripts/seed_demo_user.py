"""Seed the demo auth user via the Supabase admin API (service role key).

Idempotent: an already-registered email is reported and exits 0. Run from the
repo root (reads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from .env):

    python scripts/seed_demo_user.py
"""
import os
import sys

import httpx
from dotenv import load_dotenv

EMAIL = "maya@hagglfor.me"
PASSWORD = "HagglDemo2026!"


def main() -> int:
    load_dotenv()
    # the shared .env carries the PostgREST URL (…/rest/v1/); auth lives on the
    # bare project URL
    url = os.environ.get("SUPABASE_URL", "").rstrip("/").removesuffix("/rest/v1")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (url and key):
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
        return 1
    resp = httpx.post(
        f"{url}/auth/v1/admin/users",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        json={"email": EMAIL, "password": PASSWORD, "email_confirm": True},
        timeout=30,
    )
    if resp.status_code in (200, 201):
        print(f"created {EMAIL} (id {resp.json().get('id')})")
        return 0
    if resp.status_code == 422 or "already" in resp.text.lower():
        print(f"{EMAIL} already exists — nothing to do")
        return 0
    print(f"failed: {resp.status_code} {resp.text[:300]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
