"""Point the persona phone line at a chosen persona agent.

Run from repo root:  python3 scripts/assign_persona_number.py <persona-name> [--dry-run]

The persona line (+18576757033) is shared: only one persona answers it at a time.
This swaps which agent it rings — e.g. from persona-stonewaller to persona-supervisor
for the hero-arc demo call — by PATCHing the phone number's inbound agent_id.

Looks up the agent id by NAME (GET /v1/convai/agents, paginated + exact match) and the
persona line's phone_number_id (GET /v1/convai/phone-numbers), prints before -> after,
then PATCHes. --dry-run resolves and prints the swap without touching anything.

Safety: refuses to touch the negotiator's OUTBOUND number — that line stays outbound-only
and must never be pointed at a persona.

Reads ELEVENLABS_API_KEY from the root .env (searched upward from this file, so it works
from a git worktree too).
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.elevenlabs.io"
PERSONA_NUMBER = "+18576757033"                              # the shared inbound persona line
NEGOTIATOR_PHONE_ID = "phnum_4701kxvqv879f7d9sm8nvsg2akce"   # outbound-only — never assign a persona here


def env() -> dict[str, str]:
    """Parse the nearest .env, searching this file's directory and its parents.

    Parent discovery lets the script find the repo-root .env even when it runs from
    a git worktree checked out inside the repo directory.
    """
    for d in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        p = d / ".env"
        if p.exists():
            vals = {}
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    vals[k.strip()] = v.strip()
            return vals
    sys.exit(".env not found (searched this script's directory and its parents)")


def call(method: str, path: str, key: str, body: dict | None = None):
    req = urllib.request.Request(
        API + path, method=method,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:600]


def find_agent(key: str, name: str) -> str | None:
    """Exact-name lookup across all agent pages. `search` narrows the query (fuzzy),
    so page through and match the name exactly."""
    cursor = None
    while True:
        q = {"page_size": 100, "search": name}
        if cursor:
            q["cursor"] = cursor
        s, resp = call("GET", "/v1/convai/agents?" + urllib.parse.urlencode(q), key)
        if s != 200:
            sys.exit(f"agent list failed: {s} {resp}")
        for a in resp.get("agents", []):
            if a.get("name") == name:
                return a.get("agent_id")
        if not resp.get("has_more"):
            return None
        cursor = resp.get("next_cursor")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry = "--dry-run" in sys.argv
    if len(args) != 1:
        sys.exit("usage: python scripts/assign_persona_number.py <persona-name> [--dry-run]")
    persona = args[0]
    key = env().get("ELEVENLABS_API_KEY", "")
    if not key:
        sys.exit("ELEVENLABS_API_KEY missing from .env")

    # resolve the target agent by name
    agent_id = find_agent(key, persona)
    if not agent_id:
        s, resp = call("GET", "/v1/convai/agents?page_size=100", key)
        names = sorted(a.get("name", "") for a in resp.get("agents", [])) if s == 200 else []
        sys.exit(f"agent not found: {persona}\navailable: {names}")

    # resolve the persona phone line
    s, plist = call("GET", "/v1/convai/phone-numbers", key)
    if s != 200:
        sys.exit(f"phone-number list failed: {s} {plist}")
    plist = plist if isinstance(plist, list) else plist.get("phone_numbers", [])
    line = next((p for p in plist if p.get("phone_number") == PERSONA_NUMBER), None)
    if not line:
        sys.exit(f"persona line {PERSONA_NUMBER} not found in workspace")
    pid = line.get("phone_number_id")

    # safety: never touch the negotiator's outbound-only number
    if pid == NEGOTIATOR_PHONE_ID:
        sys.exit(f"refusing to assign: {PERSONA_NUMBER} resolved to the negotiator's "
                 f"outbound number id {NEGOTIATOR_PHONE_ID}")

    current = line.get("assigned_agent") or {}
    before = current.get("agent_id") if isinstance(current, dict) else current
    before_name = current.get("agent_name") if isinstance(current, dict) else None

    print(f"persona line : {PERSONA_NUMBER}  (id {pid})")
    print(f"target agent : {persona}  (id {agent_id})")
    print(f"before       : {before or '(unassigned)'}{f'  [{before_name}]' if before_name else ''}")
    if before == agent_id:
        print("after        : (unchanged — already assigned)")
        print("\nno swap needed." if not dry else "\n[dry-run] no swap needed.")
        return
    print(f"after        : {agent_id}  [{persona}]")

    if dry:
        print("\n[dry-run] would PATCH the persona line to the target agent. Nothing changed.")
        return

    s, resp = call("PATCH", f"/v1/convai/phone-numbers/{pid}", key, {"agent_id": agent_id})
    if s in (200, 201):
        print(f"\nassigned: {PERSONA_NUMBER} -> {persona}")
    else:
        sys.exit(f"\nPATCH failed: {s} {resp}")


if __name__ == "__main__":
    main()
