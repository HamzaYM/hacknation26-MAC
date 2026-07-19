"""Place the first real PSTN test call: negotiator agent dials the Stonewaller.

This is the agent-to-agent go/no-go (PRD §16): two ElevenLabs agents on a real
Twilio call. Run from repo root:

    python3 scripts/place_test_call.py            # negotiator → Stonewaller line
    python3 scripts/place_test_call.py +1XXXXXXX  # negotiator → any number (e.g. your cell)

Then watch/listen: ElevenLabs dashboard → Agents → Calls, or poll
GET /v1/convai/conversations. Costs ~2 voice legs (~$0.02/min total).
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STONEWALLER_NUMBER = "+18576757033"
NEGOTIATOR_PHONE_ID = "phnum_4701kxvqv879f7d9sm8nvsg2akce"


def env() -> dict[str, str]:
    vals = {}
    for line in (ROOT / ".env").read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, _, v = s.partition("=")
            vals[k.strip()] = v.strip()
    return vals


def main() -> None:
    e = env()
    to_number = sys.argv[1] if len(sys.argv) > 1 else STONEWALLER_NUMBER
    body = {
        "agent_id": e["ELEVENLABS_AGENT_ID_NEGOTIATOR"],
        "agent_phone_number_id": NEGOTIATOR_PHONE_ID,
        "to_number": to_number,
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "patient_name": "Maya Chen",
                "account_number": "MG-4471983",
                "target_entity": "Mercy General Hospital patient financial services",
                "route": "provider",
                "anchor": "657",
                "target": "876",
            }
        },
    }
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/convai/twilio/outbound-call",
        method="POST",
        headers={"xi-api-key": e["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
        data=json.dumps(body).encode(),
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print("CALL PLACED:", json.dumps(json.loads(r.read()), indent=2))
    except urllib.error.HTTPError as err:
        print("failed:", err.code, err.read().decode()[:600])


if __name__ == "__main__":
    main()
