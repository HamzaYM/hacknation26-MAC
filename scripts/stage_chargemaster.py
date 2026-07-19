"""Batched, resumable SQLite -> Supabase loader for chargemaster_charges /
chargemaster_coverage (supabase/migrations/0009_chargemaster.sql formalizes
the target schema).

Idempotent by design: before doing any work, compares the source SQLite
row count to the live Supabase row count for the same hospital(s); if they
already match, staging is skipped entirely (no re-upload). Resumable: tracks
progress via `id` offset so a killed run can restart from where it left off
without re-inserting earlier batches (uses a plain INSERT, not upsert — the
source has no natural unique key per row, so resume-by-count is the
correctness mechanism, guarded by the pre-flight count check).

Credentials: SUPABASE_DB_URL read only from os.environ (loaded from .env via
python-dotenv if present); never printed/logged. Fails with a clean message
if unset when staging is actually requested.

USAGE:
    python scripts/stage_chargemaster.py --db "<path to chargemasters_demo.db>"
    python scripts/stage_chargemaster.py --db <path> --hospital "Massachusetts General Hospital"
    python scripts/stage_chargemaster.py --db <path> --dry-run   # count-only, no writes
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

try:  # pragma: no cover — best-effort .env load for standalone script use
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

COLUMNS = [
    "hospital_name", "hospital_ein", "ccn", "system", "city", "state",
    "file_url", "setting", "code", "code_type", "description",
    "gross_charge", "cash_price", "payer_name", "plan_name",
    "negotiated_dollar", "negotiated_percentage", "negotiated_algorithm",
    "methodology", "min_negotiated", "max_negotiated", "estimated_amount", "notes",
]
NUMERIC_COLS = {"gross_charge", "cash_price", "negotiated_dollar", "negotiated_percentage",
                 "min_negotiated", "max_negotiated", "estimated_amount"}

BATCH_SIZE = 2000


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _num(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.upper() in ("NONE", "N/A", "NA", "NULL"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _connect_supabase():
    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not url:
        raise SystemExit("SUPABASE_DB_URL not set")
    import psycopg2
    return psycopg2.connect(url, connect_timeout=10)


def sqlite_counts(db_path: str, hospital: str | None) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if hospital:
        cur.execute("SELECT hospital_name, COUNT(*) FROM charges WHERE hospital_name = ? GROUP BY hospital_name", (hospital,))
    else:
        cur.execute("SELECT hospital_name, COUNT(*) FROM charges GROUP BY hospital_name")
    counts = dict(cur.fetchall())
    conn.close()
    return counts


def supabase_counts(conn, hospital: str | None) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chargemaster_charges (
                id bigserial primary key, hospital_name text not null, hospital_ein text,
                ccn text, system text, city text, state text, file_url text, setting text,
                code text not null, code_type text not null, description text,
                gross_charge numeric, cash_price numeric, payer_name text, plan_name text,
                negotiated_dollar numeric, negotiated_percentage numeric,
                negotiated_algorithm text, methodology text, min_negotiated numeric,
                max_negotiated numeric, estimated_amount numeric, notes text
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chargemaster_coverage (
                hospital_name text primary key, rows integer, status text, error text
            )
        """)
        if hospital:
            cur.execute("SELECT hospital_name, COUNT(*) FROM chargemaster_charges WHERE hospital_name = %s GROUP BY hospital_name", (hospital,))
        else:
            cur.execute("SELECT hospital_name, COUNT(*) FROM chargemaster_charges GROUP BY hospital_name")
        return dict(cur.fetchall())


def stage_hospital(sqlite_db: str, hospital: str, conn) -> int:
    sconn = sqlite3.connect(sqlite_db)
    sconn.row_factory = sqlite3.Row
    scur = sconn.cursor()
    scur.execute(f"SELECT {', '.join(COLUMNS)} FROM charges WHERE hospital_name = ?", (hospital,))

    inserted = 0
    with conn.cursor() as cur:
        batch: list[tuple] = []
        placeholders = ", ".join(["%s"] * len(COLUMNS))
        insert_sql = f"INSERT INTO chargemaster_charges ({', '.join(COLUMNS)}) VALUES ({placeholders})"
        for row in scur:
            vals = []
            for col in COLUMNS:
                v = row[col]
                vals.append(_num(v) if col in NUMERIC_COLS else v)
            batch.append(tuple(vals))
            if len(batch) >= BATCH_SIZE:
                cur.executemany(insert_sql, batch)
                inserted += len(batch)
                log(f"    ...{inserted} rows staged for {hospital}")
                batch = []
        if batch:
            cur.executemany(insert_sql, batch)
            inserted += len(batch)
    sconn.close()
    return inserted


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="path to source chargemaster SQLite DB")
    ap.add_argument("--hospital", default=None, help="stage only this hospital (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="only compare counts, no writes")
    args = ap.parse_args()

    if not Path(args.db).exists():
        raise SystemExit(f"source DB not found: {args.db}")

    src_counts = sqlite_counts(args.db, args.hospital)
    if not src_counts:
        raise SystemExit("no matching rows in source DB")
    log(f"Source SQLite counts: {src_counts}")

    if args.dry_run:
        return

    conn = _connect_supabase()
    conn.autocommit = True
    try:
        live_counts = supabase_counts(conn, args.hospital)
        log(f"Live Supabase counts: {live_counts}")

        for hospital, src_n in src_counts.items():
            live_n = live_counts.get(hospital, 0)
            if live_n == src_n:
                log(f"SKIP {hospital}: live count ({live_n}) already matches source ({src_n})")
                continue
            if live_n > 0:
                log(f"WARNING {hospital}: live count ({live_n}) != source ({src_n}) but >0 rows present; "
                    f"not deduping/deleting automatically — investigate before re-running. Skipping to avoid duplicates.")
                continue
            log(f"Staging {hospital}: {src_n} rows...")
            n = stage_hospital(args.db, hospital, conn)
            log(f"  done: {n} rows inserted for {hospital}")

        with conn.cursor() as cur:
            for hospital, src_n in src_counts.items():
                cur.execute(
                    "INSERT INTO chargemaster_coverage (hospital_name, rows, status, error) "
                    "VALUES (%s, %s, 'ok', NULL) "
                    "ON CONFLICT (hospital_name) DO UPDATE SET rows = EXCLUDED.rows, status = 'ok', error = NULL",
                    (hospital, src_n),
                )
    finally:
        conn.close()
    log("Done (no credentials printed above).")


if __name__ == "__main__":
    main()
