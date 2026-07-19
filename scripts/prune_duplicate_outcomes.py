"""Prune duplicate demo outcomes (accumulated across repeated sim runs).

Keeps the NEWEST outcome per (entity, outcome_type); never touches the two
archived real calls. Findings source: E2E audit — the demo case had 15
outcomes (4x identical Meridian settlements, 6x Mercy declines) after a day
of test launches, cluttering the case file's paper trail.

    apps/api/.venv/bin/python scripts/prune_duplicate_outcomes.py            # dry run
    apps/api/.venv/bin/python scripts/prune_duplicate_outcomes.py --apply    # delete
"""
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PROTECTED_CALLS = (
    "e0c2e6e2-785e-45eb-b71f-dbbc1d7f6185",  # archived real human call (audio)
    "b049442e-8dc0-4ceb-ba80-d3946f357765",  # archived real a2a call (audio)
)

RANKED_SQL = """
with ranked as (
  select o.id, o.call_id,
         coalesce(d.target_entity, 'unknown') as entity, o.outcome_type,
         row_number() over (partition by coalesce(d.target_entity, 'unknown'), o.outcome_type
                            order by c.started_at desc nulls last) as rn
  from outcomes o
  join calls c on c.id = o.call_id
  left join strategy_dossiers d on d.id = c.dossier_id
  where o.call_id not in %s
)
select id, entity, outcome_type from ranked where rn > 1
"""


def main() -> None:
    apply = "--apply" in sys.argv
    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(RANKED_SQL, (PROTECTED_CALLS,))
    rows = cur.fetchall()
    for row in rows:
        print(("DELETE " if apply else "would delete ") + f"{row[0]}  {row[1]} / {row[2]}")
    if not rows:
        print("nothing to prune")
        return
    if apply:
        cur.execute("delete from outcomes where id in %s", (tuple(r[0] for r in rows),))
        print(f"pruned {len(rows)} duplicate outcome(s)")
    else:
        print(f"{len(rows)} duplicate(s) found — rerun with --apply to delete")


if __name__ == "__main__":
    main()
