"""Reviewed cleanup for the live Supabase DEMO case (Hamza runs --apply).

QA on the demo case (00000000-0000-0000-0000-000000000001) found:
  * ~80+ `calls` rows stuck non-terminal with zero `call_events` — they render
    as forever-LIVE ghost cards in the War Room overview.
  * 14 `outcomes` where the curated set is ~6: the same settlement triplicated
    ($980->$392 x3, a charity application x3, a documented decline x3) plus one
    garbage row (rep name "Chinnaswamy Muthuswamy Vinagopali Reddy", a raw
    war-room id as the reference number).

This groups the changes and, by default, prints exactly what it WOULD do. Pass
--apply to execute. It is idempotent — safe to run twice.

    apps/api/.venv/bin/python scripts/demo_reset.py            # dry run (default)
    apps/api/.venv/bin/python scripts/demo_reset.py --apply    # execute (Hamza)

Safety rails (never crossed):
  * A call with transcript events or a recording_path is a curated archived real
    call — never deleted, never re-statused. Ghost deletes require zero events
    AND no recording AND no outcome; stale mark-ended requires no transcript AND
    no recording.
  * Duplicate-outcome pruning keeps the EARLIEST of each group and never prunes
    an outcome whose call has a recording (that would drop the audio off /report).
  * Only `calls` and `outcomes` on the demo case are touched — cases,
    authorizations and every other row are left alone.

Ends with a recordings audit: every call with a recording_path on the demo case
(flagged if fewer than 6), plus which surviving archived calls still lack audio
so the coordinator can re-run scripts/archive_call.py on them.

Reads SUPABASE_DB_URL from the repo-root .env (via dotenv), same as
scripts/prune_duplicate_outcomes.py.
"""
import os
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEMO_CASE_ID = "00000000-0000-0000-0000-000000000001"

# Ghost = stuck non-terminal AND pure noise (no events, no recording, no outcome).
GHOST_WHERE = """
  case_id = %(case)s
  and status not in ('ended', 'failed')
  and recording_path is null
  and not exists (select 1 from call_events e where e.call_id = calls.id)
  and not exists (select 1 from outcomes  o where o.call_id = calls.id)
"""

# Stale = non-terminal, has telemetry but no transcript and no recording (so it is
# not a curated archived call). These keep their events; we only close the status.
STALE_WHERE = """
  case_id = %(case)s
  and status not in ('ended', 'failed')
  and recording_path is null
  and exists (select 1 from call_events e where e.call_id = calls.id)
  and not exists (select 1 from call_events e
                  where e.call_id = calls.id and e.type = 'transcript')
"""

# Every outcome on the demo case, with the call facts the grouping needs.
OUTCOMES_SQL = """
select o.id, o.outcome_type, o.original_amount, o.final_amount,
       o.reference_number, o.rep_name,
       coalesce(d.target_entity, 'unknown') as entity,
       c.id as call_id, c.started_at, c.recording_path,
       (select count(*) from call_events e
        where e.call_id = c.id and e.type = 'transcript') as transcript_events
from outcomes o
join calls c on c.id = o.call_id
left join strategy_dossiers d on d.id = c.dossier_id
where c.case_id = %(case)s
"""

_UUID_FRAGMENT = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}")


def garbage_reasons(rep_name, reference_number):
    """Why this outcome reads as garbage (empty list = clean). Real references are
    short codes (MRS-55217, BSEP-FA-1102) and real rep names are 1-2 words."""
    reasons = []
    ref = reference_number or ""
    if "WARROUM" in ref.upper():
        reasons.append("reference contains WARROUM")
    if _UUID_FRAGMENT.search(ref):
        reasons.append("reference embeds a raw id")
    name = (rep_name or "").strip()
    if name and len(name.split()) >= 4:
        reasons.append(f"rep name is {len(name.split())} words")
    return reasons


def _amt(v):
    return "-" if v is None else f"{float(v):.2f}"


def main() -> int:
    apply = "--apply" in sys.argv

    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not url:
        print("SUPABASE_DB_URL missing — nothing to do.")
        return 1
    try:
        conn = psycopg2.connect(url, connect_timeout=15)
    except psycopg2.OperationalError as err:
        print(f"Supabase unreachable: {str(err).splitlines()[0]}")
        return 1
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)
    params = {"case": DEMO_CASE_ID}

    print(f"DEMO DATA RESET — {'APPLYING' if apply else 'dry run (pass --apply to execute)'}")
    print(f"case {DEMO_CASE_ID}\n")

    # ── [1] ghost calls → delete ─────────────────────────────────────────────
    cur.execute(f"select id, status, started_at from calls where {GHOST_WHERE} "
                "order by started_at nulls first", params)
    ghosts = cur.fetchall()
    print(f"[1] GHOST CALLS (non-terminal · zero events · no recording) — "
          f"{len(ghosts)} to delete")
    for r in ghosts[:12]:
        print(f"      {r['id']}  status={r['status']:<9} started={r['started_at'] or '-'}")
    if len(ghosts) > 12:
        print(f"      … and {len(ghosts) - 12} more")
    if apply and ghosts:
        cur.execute(f"delete from calls where {GHOST_WHERE}", params)
        print(f"    deleted {cur.rowcount} ghost call(s)")

    # ── [2] stale non-terminal calls → mark ended ────────────────────────────
    cur.execute(f"select id, status, started_at, "
                f"(select count(*) from call_events e where e.call_id = calls.id) as events "
                f"from calls where {STALE_WHERE} order by started_at nulls first", params)
    stale = cur.fetchall()
    print(f"\n[2] STALE NON-TERMINAL CALLS (events, no transcript/recording) — "
          f"{len(stale)} to mark ended")
    for r in stale:
        print(f"      {r['id']}  status={r['status']:<9} events={r['events']} "
              f"started={r['started_at'] or '-'}")
    if apply and stale:
        cur.execute(f"update calls set status = 'ended', "
                    f"ended_at = coalesce(ended_at, now()) where {STALE_WHERE}", params)
        print(f"    marked {cur.rowcount} call(s) ended")

    # ── outcomes: split into keep / prune-duplicate / garbage ────────────────
    cur.execute(OUTCOMES_SQL, params)
    outcomes = cur.fetchall()

    garbage, clean = [], []
    for o in outcomes:
        reasons = garbage_reasons(o["rep_name"], o["reference_number"])
        (garbage if reasons else clean).append((o, reasons))

    # Duplicate grouping over the non-garbage rows: identical substantive outcome.
    groups: dict = {}
    for o, _ in clean:
        key = (o["outcome_type"], o["entity"], _amt(o["original_amount"]), _amt(o["final_amount"]))
        groups.setdefault(key, []).append(o)

    dup_prune = []          # (outcome, kept_id)
    dup_display = []        # (key, kept, [pruned])
    for key, rows in groups.items():
        rows.sort(key=lambda o: (o["started_at"] is None, o["started_at"]))
        kept = rows[0]                                   # earliest survives
        pruned = [o for o in rows[1:] if o["recording_path"] is None]  # never prune a recording
        if pruned:
            dup_display.append((key, kept, pruned))
            dup_prune.extend((o, kept["id"]) for o in pruned)

    # ── [3] duplicate outcomes → prune (keep earliest) ───────────────────────
    print(f"\n[3] DUPLICATE OUTCOMES (keep earliest per group) — {len(dup_prune)} to prune")
    for key, kept, pruned in dup_display:
        otype, entity, orig, final = key
        label = f"{otype} · {entity} · {orig}->{final}" if final != "-" else f"{otype} · {entity}"
        print(f"      {label}")
        print(f"        keep  {kept['id']}  started={kept['started_at'] or '-'}")
        for o in pruned:
            print(f"        prune {o['id']}  started={o['started_at'] or '-'}")
    if apply and dup_prune:
        ids = tuple(o["id"] for o, _ in dup_prune)
        cur.execute("delete from outcomes where id in %s", (ids,))
        print(f"    pruned {cur.rowcount} duplicate outcome(s)")

    # ── [4] garbage outcomes → delete ────────────────────────────────────────
    print(f"\n[4] GARBAGE OUTCOMES (WARROUM / raw-id ref · absurd rep name) — "
          f"{len(garbage)} to delete")
    for o, reasons in garbage:
        print(f"      {o['id']}  rep={o['rep_name']!r}")
        print(f"        ref={o['reference_number']!r}")
        print(f"        reason: {', '.join(reasons)}")
    if apply and garbage:
        ids = tuple(o["id"] for o, _ in garbage)
        cur.execute("delete from outcomes where id in %s", (ids,))
        print(f"    deleted {cur.rowcount} garbage outcome(s)")

    # ── recordings audit (read-only) ─────────────────────────────────────────
    deleted_outcome_ids = {o["id"] for o, _ in dup_prune} | {o["id"] for o, _ in garbage}
    survivors = [o for o in outcomes if o["id"] not in deleted_outcome_ids]
    survivor_call_ids = {o["call_id"] for o in survivors}

    cur.execute("select id, recording_path, "
                "(select count(*) from call_events e where e.call_id = calls.id "
                " and e.type = 'transcript') as transcript_events "
                "from calls where case_id = %(case)s and recording_path is not null "
                "order by started_at nulls first", params)
    recordings = cur.fetchall()

    print("\nRECORDINGS AUDIT")
    print(f"  calls with a recording_path on the demo case: {len(recordings)}")
    for r in recordings:
        on_report = "on /report" if r["id"] in survivor_call_ids else "no surviving outcome"
        print(f"      {r['id']}  transcript_events={r['transcript_events']:<4} {on_report}")
    if len(recordings) < 6:
        print(f"  ** FLAG: fewer than 6 recordings on the demo case ({len(recordings)}). **")

    players = sum(1 for o in survivors if o["recording_path"])
    print(f"  audio players that will render on /report after cleanup: {players}")

    re_archive = [o for o in survivors
                  if o["recording_path"] is None and o["transcript_events"] > 0]
    print(f"  archived calls that survive an outcome but LACK a recording "
          f"(re-run scripts/archive_call.py): {len(re_archive)}")
    for o in re_archive:
        print(f"      call {o['call_id']}  transcript_events={o['transcript_events']}  "
              f"({o['outcome_type']} · {o['entity']})")

    if not apply:
        print("\n(dry run — nothing was written. Re-run with --apply to execute.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
