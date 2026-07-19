"""One-time DATA cleanup: close stale, orphaned calls.

    python3 scripts/db_mark_stale_calls.py [--dry-run]

The War Room overview renders every non-terminal `calls` row. A launch that never
streamed (or an old fallback row) lingers there as a dead "live/connecting" card
forever. This marks such calls ended so the overview stays honest.

Stale = status NOT in (ended, failed) AND no `call_events` in the last 30 minutes
(covers both zero-event orphans and calls whose last event is long past). The two
archived REAL calls (id prefixes e0c2e6e2- and b049442e-) are always excluded.

Reads SUPABASE_DB_URL from the repo-root .env (via dotenv). Best-effort: prints a
clear message and exits non-zero if the DB is unreachable.
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

# Archived real calls — never auto-close these (they're the marquee recordings).
ARCHIVED_PREFIXES = ("e0c2e6e2", "b049442e")

# A call with no events in this window counts as stale.
STALE_WINDOW = "30 minutes"

_WHERE = f"""
  status not in ('ended', 'failed')
  and id::text not like 'e0c2e6e2%'
  and id::text not like 'b049442e%'
  and not exists (
    select 1 from call_events e
    where e.call_id = calls.id
      and e.ts > now() - interval '{STALE_WINDOW}'
  )
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would be closed without writing")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    from app import db

    if not db.available():
        print("SUPABASE_DB_URL missing or unreachable — nothing to do.")
        return 1

    preview = db._run(
        f"""
        select id, case_id, counterparty, status, started_at,
               (select count(*) from call_events e where e.call_id = calls.id) as total_events,
               (select max(ts) from call_events e where e.call_id = calls.id) as last_event_at
        from calls
        where {_WHERE}
        order by started_at nulls first
        """,
        fetch=True,
    )
    preview = preview or []

    if not preview:
        print("No stale non-terminal calls found — nothing to close.")
        return 0

    print(f"{len(preview)} stale call(s) matched (excluding archived {', '.join(p + '-' for p in ARCHIVED_PREFIXES)}):")
    for r in preview:
        print(f"  {r['id']}  status={r['status']:<8} counterparty={r['counterparty']:<6} "
              f"events={r['total_events']:<3} last_event={r['last_event_at'] or '—'} started={r['started_at'] or '—'}")

    if args.dry_run:
        print("\n--dry-run: no changes written.")
        return 0

    closed = db._run(
        f"""
        update calls
        set status = 'ended', ended_at = coalesce(ended_at, now())
        where {_WHERE}
        returning id
        """,
        fetch=True,
    )
    closed = closed or []
    print(f"\nClosed {len(closed)} call(s) → status='ended'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
