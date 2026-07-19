"""Archive a finished ElevenLabs conversation into the product (idempotent).

    python3 scripts/archive_call.py <conversation_id> [--counterparty human]

Fetches the transcript (GET /v1/convai/conversations/{id}) and full audio
(…/audio) from ElevenLabs, then:
  1. finds the `calls` row by elevenlabs_conversation_id — or creates one
     against the demo case, stamping real started_at/ended_at from metadata;
  2. inserts the transcript turns as `transcript` call_events (skipped if the
     call already has transcript events);
  3. uploads the audio to the recordings bucket via app.storage (which
     normalizes the /rest/v1-suffixed SUPABASE_URL) and sets recording_path;
  4. stages an outcomes row when the ending is determinable: a call that
     closed with no settlement (hang-up / stonewall-transfer loop, per the
     conversation analysis) archives as documented_decline + callback, with
     the transcript events as evidence. Anything else: no outcome inserted.

After a run, /report plays the real audio and /warroom?call_id=<id> replays
the transcript.
"""
import argparse
import sys
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

ELEVEN_BASE = "https://api.elevenlabs.io/v1/convai/conversations"

# Deterministic "ended with no settlement" signals in the post-call analysis
# summary — the only outcome shape we auto-archive (everything else needs a
# human to read the call).
NO_SETTLEMENT_SIGNALS = (
    "ended the call", "hung up", "stonewall", "unresolved",
    "transfers to supervisors", "without a resolution",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("conversation_id")
    parser.add_argument("--counterparty", choices=("agent", "human"), default="agent",
                        help="who was on the far end (a2a persona: agent · role-play: human)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    import os

    from app import db, storage
    from app.fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC

    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        print("ELEVENLABS_API_KEY not set")
        return 1
    if not db.available():
        print("SUPABASE_DB_URL missing or unreachable")
        return 1

    cid = args.conversation_id
    resp = httpx.get(f"{ELEVEN_BASE}/{cid}", headers={"xi-api-key": api_key}, timeout=30)
    if resp.status_code != 200:
        print(f"conversation fetch failed: {resp.status_code} {resp.text[:200]}")
        return 1
    convo = resp.json()
    meta = convo.get("metadata") or {}

    # 1 ── calls row (find by conversation_id, else create against the demo case)
    call = db.get_call_by_conversation(cid)
    if call is None:
        call_id = str(uuid.uuid4())
        db.ensure_demo_case()
        db.insert_call(call_id, DEMO_CASE_ID, counterparty=args.counterparty, status="ended")
        db.set_call_conversation(call_id, cid)
        started = meta.get("start_time_unix_secs")
        duration = meta.get("call_duration_secs")
        if started:
            db._run(
                "update calls set started_at = to_timestamp(%s), "
                "ended_at = to_timestamp(%s) where id = %s",
                (started, started + (duration or 0), call_id),
            )
        print(f"calls row created: {call_id}")
    else:
        call_id = str(call["id"])
        db.update_call_status(call_id, "ended")
        print(f"calls row found:   {call_id}")

    # 2 ── transcript → call_events (skip if this call already has them)
    existing = db._run(
        "select count(*) as n from call_events where call_id = %s and type = 'transcript'",
        (call_id,), fetch=True,
    )
    event_ids: list[int] = []
    if existing and existing[0]["n"]:
        print(f"transcript events exist ({existing[0]['n']}) — skipping insert")
    else:
        for turn in convo.get("transcript") or []:
            text = turn.get("message")
            if not text:
                continue
            speaker = "agent" if turn.get("role") == "agent" else "rep"
            event_id = db.insert_event(call_id, "transcript", {"speaker": speaker, "text": text})
            if event_id is not None:
                event_ids.append(event_id)
        print(f"transcript events inserted: {len(event_ids)}")

    # 3 ── audio → recordings bucket → calls.recording_path
    audio_landed = False
    audio_resp = httpx.get(f"{ELEVEN_BASE}/{cid}/audio", headers={"xi-api-key": api_key}, timeout=120)
    if audio_resp.status_code == 200 and audio_resp.content:
        path = storage.store_recording(call_id, audio_resp.content)
        if path:
            db.set_call_recording(call_id, path)
            audio_landed = True
            print(f"audio stored: {path} ({len(audio_resp.content)} bytes)")
        else:
            print("audio upload FAILED (see storage warnings)")
    else:
        print(f"audio fetch failed: {audio_resp.status_code}")

    # 4 ── outcome, only when determinable (no-settlement close)
    have_outcome = db._run("select count(*) as n from outcomes where call_id = %s",
                           (call_id,), fetch=True)
    if have_outcome and have_outcome[0]["n"]:
        print("outcome row exists — skipping")
    else:
        summary = ((convo.get("analysis") or {}).get("transcript_summary") or "").lower()
        if any(s in summary for s in NO_SETTLEMENT_SIGNALS):
            db.insert_outcome({
                "call_id": call_id,
                "outcome_type": "documented_decline",
                "original_amount": DEMO_JOB_SPEC["bill"]["patient_balance"],
                "final_amount": None,
                "reduction_pct": None,
                "winning_lever": None,
                "reference_number": None,
                "rep_name": None,
                "next_action": "callback",
                "evidence_event_ids": event_ids,
            })
            print("outcome staged: documented_decline (no settlement reached) → callback")
        else:
            print("outcome not determinable from the analysis — none inserted")

    print(f"report: https://hagglfor.me/report · war room: https://hagglfor.me/warroom?call_id={call_id}")
    return 0 if audio_landed else 1


if __name__ == "__main__":
    sys.exit(main())
