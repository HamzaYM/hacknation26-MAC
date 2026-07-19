"""Idempotent Twilio number provisioning + ElevenLabs import.

Run from repo root:  python3 scripts/provision_twilio.py [--count 2]

PREREQ: Twilio paid account with an APPROVED Trust Hub primary customer profile
(number purchases fail with error 20003 until KYC is approved — console task).

Does, in order (skipping anything that already exists):
  1. Buys `--count` MA local voice numbers (area codes 857/339/351/781/508/413)
     — first one labeled `negotiator` → written to TWILIO_PHONE_NUMBER in .env;
     the rest labeled persona-N.
  2. Imports every owned number into ElevenLabs (native Twilio integration).
  3. Assigns inbound agents: persona numbers → persona agents (in roster order
     from scripts/provision_elevenlabs.py); negotiator number stays outbound-only.
Prints a summary table at the end.
"""
from __future__ import annotations

import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MA_AREA_CODES = ["857", "339", "351", "781", "508", "413"]
PERSONA_ORDER = ["persona-stonewaller", "persona-policy-citer", "persona-no-authority", "persona-collections"]


def env() -> dict[str, str]:
    vals = {}
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip()
    return vals


def tw(method: str, path: str, e: dict, data: dict | None = None):
    auth = base64.b64encode(f"{e['TWILIO_ACCOUNT_SID']}:{e['TWILIO_AUTH_TOKEN']}".encode()).decode()
    url = f"https://api.twilio.com/2010-04-01/Accounts/{e['TWILIO_ACCOUNT_SID']}{path}"
    req = urllib.request.Request(url, method=method, headers={"Authorization": f"Basic {auth}"},
                                 data=urllib.parse.urlencode(data).encode() if data else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()[:400]


def el(method: str, path: str, e: dict, body: dict | None = None):
    req = urllib.request.Request("https://api.elevenlabs.io" + path, method=method,
                                 headers={"xi-api-key": e["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()[:400]


def main() -> None:
    count = int(sys.argv[sys.argv.index("--count") + 1]) if "--count" in sys.argv else 2
    e = env()
    for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "ELEVENLABS_API_KEY"):
        if not e.get(k):
            sys.exit(f"{k} missing from .env")

    # 1 ── buy numbers (idempotent: count existing first)
    s, owned = tw("GET", "/IncomingPhoneNumbers.json?PageSize=50", e)
    if s != 200:
        sys.exit(f"list owned numbers failed: {s} {owned}")
    owned_nums = owned["incoming_phone_numbers"]
    print(f"owned numbers: {[n['phone_number'] for n in owned_nums]}")

    to_buy = max(0, count - len(owned_nums))
    for i in range(to_buy):
        bought = False
        for ac in MA_AREA_CODES:
            s, avail = tw("GET", f"/AvailablePhoneNumbers/US/Local.json?AreaCode={ac}&VoiceEnabled=true&PageSize=3", e)
            if s != 200 or not avail.get("available_phone_numbers"):
                continue
            number = avail["available_phone_numbers"][0]["phone_number"]
            label = "negotiator" if not owned_nums and i == 0 else f"persona-{len(owned_nums) + i}"
            s, resp = tw("POST", "/IncomingPhoneNumbers.json", e, {"PhoneNumber": number, "FriendlyName": label})
            if s in (200, 201):
                print(f"BOUGHT {resp['phone_number']} ({label})")
                owned_nums.append(resp)
                bought = True
                break
            print(f"buy {number} failed: {s} {resp}")
            if isinstance(resp, str) and "20003" in resp:
                sys.exit("BLOCKED: Trust Hub KYC not approved yet (error 20003). "
                         "Console → Trust Hub → complete the primary customer profile, then re-run.")
        if not bought:
            sys.exit("no MA numbers purchasable right now")

    numbers = [n["phone_number"] for n in owned_nums]
    negotiator_number, persona_numbers = numbers[0], numbers[1:]

    # write TWILIO_PHONE_NUMBER
    env_path = ROOT / ".env"
    text = env_path.read_text()
    text = re.sub(r"^TWILIO_PHONE_NUMBER=.*$", f"TWILIO_PHONE_NUMBER={negotiator_number}", text, flags=re.M)
    env_path.write_text(text)
    print(f"TWILIO_PHONE_NUMBER={negotiator_number} written to .env")

    # 2 ── import into ElevenLabs (idempotent by phone number)
    s, existing = el("GET", "/v1/convai/phone-numbers", e)
    have = {p.get("phone_number") for p in (existing if isinstance(existing, list) else existing.get("phone_numbers", []))} if s == 200 else set()
    imported: dict[str, str] = {}  # phone -> phone_number_id
    for num in numbers:
        if num in have:
            print(f"already imported: {num}")
            continue
        s, resp = el("POST", "/v1/convai/phone-numbers/create", e, {
            "provider": "twilio", "phone_number": num,
            "label": "negotiator" if num == negotiator_number else "persona",
            "sid": e["TWILIO_ACCOUNT_SID"], "token": e["TWILIO_AUTH_TOKEN"],
        })
        if s in (200, 201):
            imported[num] = resp.get("phone_number_id", "?")
            print(f"imported to ElevenLabs: {num} → {imported[num]}")
        else:
            print(f"import failed for {num}: {s} {resp} — check the endpoint shape against current docs")

    # 3 ── assign persona agents to persona numbers (roster order)
    s, agents = el("GET", "/v1/convai/agents?page_size=100", e)
    by_name = {a["name"]: a["agent_id"] for a in agents.get("agents", [])} if s == 200 else {}
    s, plist = el("GET", "/v1/convai/phone-numbers", e)
    plist = plist if isinstance(plist, list) else plist.get("phone_numbers", [])
    pid_by_number = {p.get("phone_number"): p.get("phone_number_id") for p in plist}
    for num, persona in zip(persona_numbers, PERSONA_ORDER):
        pid, agent_id = pid_by_number.get(num), by_name.get(persona)
        if not pid or not agent_id:
            print(f"skip assign {num} → {persona} (missing id)")
            continue
        s, resp = el("PATCH", f"/v1/convai/phone-numbers/{pid}", e, {"agent_id": agent_id})
        print(f"assign {num} → {persona}: {'ok' if s in (200, 201) else (s, resp)}")

    print("\nSummary:")
    print(f"  outbound (negotiator): {negotiator_number}")
    for num, persona in zip(persona_numbers, PERSONA_ORDER):
        print(f"  inbound  {num} → {persona}")


if __name__ == "__main__":
    main()
