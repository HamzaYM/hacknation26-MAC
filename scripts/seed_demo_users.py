"""Seed the three demo logins + their cases rows (idempotent).

maya@hagglfor.me / dan@hagglfor.me / nina@hagglfor.me — all HagglDemo2026!.
Each owns one fixture case via cases.owner_email (migration 0002):
  maya → the existing demo case (…0001) · dan → …0002 · nina → …0003
Supersedes scripts/seed_demo_user.py (maya only).

Run from the repo root (reads .env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
SUPABASE_ANON_KEY, SUPABASE_DB_URL):

    python scripts/seed_demo_users.py

Exits 0 only when every auth user exists, every cases row carries its
owner_email, and a password-grant sign-in succeeds for all three accounts.
"""
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

PASSWORD = "HagglDemo2026!"


def main() -> int:
    load_dotenv(ROOT / ".env")
    from app import db
    from app.fixtures_users import OWNER_EMAIL_BY_CASE_ID, SPEC_BY_CASE_ID

    # the shared .env carries the PostgREST URL (…/rest/v1/); auth lives on the
    # bare project URL
    url = os.environ.get("SUPABASE_URL", "").rstrip("/").removesuffix("/rest/v1")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
    if not (url and service_key and anon_key):
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY not set")
        return 1
    if not db.available():
        print("SUPABASE_DB_URL missing or unreachable — cases rows need it")
        return 1

    ok = True
    for case_id, email in OWNER_EMAIL_BY_CASE_ID.items():
        # 1 ── auth user via the admin API (already-registered → fine)
        resp = httpx.post(
            f"{url}/auth/v1/admin/users",
            headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
            json={"email": email, "password": PASSWORD, "email_confirm": True},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            print(f"auth user created: {email}")
        elif resp.status_code == 422 or "already" in resp.text.lower():
            print(f"auth user exists:  {email}")
        else:
            print(f"auth user FAILED:  {email} → {resp.status_code} {resp.text[:200]}")
            ok = False

        # 2 ── cases row upsert; owner_email lands on new AND existing rows
        if db.ensure_case(case_id, SPEC_BY_CASE_ID[case_id], email):
            print(f"case row ensured:  {case_id} ← {email}")
        else:
            print(f"case row FAILED:   {case_id}")
            ok = False

    # 3 ── verify: password-grant sign-in (exactly what the web login does)
    for email in OWNER_EMAIL_BY_CASE_ID.values():
        resp = httpx.post(
            f"{url}/auth/v1/token?grant_type=password",
            headers={"apikey": anon_key, "Content-Type": "application/json"},
            json={"email": email, "password": PASSWORD},
            timeout=30,
        )
        signed_in = resp.status_code == 200 and bool(resp.json().get("access_token"))
        print(f"sign-in {'ok:    ' if signed_in else 'FAILED:'} {email}")
        ok = ok and signed_in

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
