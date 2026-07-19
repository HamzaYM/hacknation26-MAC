"""Place a real PSTN test call: negotiator agent dials the Stonewaller.

This is the agent-to-agent go/no-go (PRD §16): two ElevenLabs agents on a real
Twilio call. Run from repo root (needs the api deps, e.g. ./.venv/bin/python):

    python3 scripts/place_test_call.py            # negotiator → Stonewaller line
    python3 scripts/place_test_call.py +1XXXXXXX  # negotiator → any number (e.g. your cell)

The `calls` row is created BEFORE dialing and the ElevenLabs conversation_id
is persisted on it (POST /calls/place-real code path), so mid-call tool events
and the post-call webhook (transcript + audio) land in-product — watch it live
at the printed War Room URL. Costs ~2 voice legs (~$0.02/min total).
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def main() -> None:
    load_dotenv(ROOT / ".env")
    # this script's whole point is a real dial — flip the feature flag on
    os.environ.setdefault("ELEVENLABS_OUTBOUND_ENABLED", "1")
    from app.routers.calls import PlaceRealRequest, place_real_call

    to_number = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        out = place_real_call(PlaceRealRequest(to_number=to_number))
    except Exception as err:  # noqa: BLE001 — surface HTTP/dial errors plainly
        print("failed:", err)
        raise SystemExit(1) from err

    print(f"calls row created: {out['call_id']} (case {out['case_id']})")
    print(f"dialed {out['to_number']} → conversation_id: {out.get('conversation_id')}")
    if out.get("note"):
        print("note:", out["note"])
    print(f"watch live: {out['war_room_url']}")


if __name__ == "__main__":
    main()
