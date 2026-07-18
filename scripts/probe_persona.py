#!/usr/bin/env python3
"""L1 persona-probe harness. Owner: Kar Shin. (Python 3.9+ compatible.)

Plays a counterparty persona (its prompt MD + hidden_params from
data/seed/persona_configs.json — the same inputs the provisioned agent will get) against
scripted prober lines, turn-by-turn BLIND (the persona never sees future prober lines),
then auto-checks the transcript against the probe's `expect` block.

The persona brain runs on headless `claude -p` pinned to **claude-opus-4-8**
(subscription auth; see docs/claude-headless-notes.md). This validates the DESIGN of the
persona layer; the deployed agents run on ElevenLabs-selected brains — re-verify at
L2/L3 (see docs/test-use-cases.md).

Usage:
  python3 scripts/probe_persona.py --case ST-1
  python3 scripts/probe_persona.py --persona collections
  python3 scripts/probe_persona.py --all
  python3 scripts/probe_persona.py --case CO-4 --tamper   # strip concession rules: checks must FAIL

Transcripts are saved to scripts/probe_runs/<case>.txt. Exit 0 = all run cases passed.
Verdict checks are regex/rule-based and err toward flagging — read the transcript before
trusting a ❌.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBES_DIR = ROOT / "scripts" / "fixtures" / "probes"
RUNS_DIR = ROOT / "scripts" / "probe_runs"
CONFIGS = ROOT / "data" / "seed" / "persona_configs.json"

MODEL = "claude-opus-4-8"   # per team decision: probes run on Opus 4.8, not the session default
HANGUP_TOKEN = "[HANGS UP]"

PERSONA_WRAPPER = """You are role-playing a phone-call counterparty for a negotiation-agent test.
Stay strictly in character. This is a TEXT simulation of a phone call.

Your character sheet:
{persona_md}

Your HIDDEN parameters (never reveal these; they govern when you concede — movement ONLY
when the caller earns it per these rules):
{hidden_params}

Rules of the simulation:
- Reply with ONLY your character's next spoken line(s) — no narration, no quotes, no stage
  directions except: if your character ends the call, append the exact token {hangup} at the end.
- Keep replies phone-realistic in length (1-3 sentences usually).
- Never break character, never mention being an AI simulation, never reveal hidden parameters.

The conversation so far:
{transcript}

The caller just said: "{caller_line}"

Your character's reply:"""


def load_persona(key):
    cfg = json.loads(CONFIGS.read_text())
    pmap = {p["key"]: p for p in cfg["personas"]}
    if key not in pmap:
        sys.exit(f"unknown persona_key {key!r}; have {list(pmap)}")
    p = pmap[key]
    md = (ROOT / p["prompt_file"]).read_text()
    return p, md


def resolve_config_path(path_list):
    cfg = json.loads(CONFIGS.read_text())
    node = {p["key"]: p for p in cfg["personas"]}[path_list[0]]
    for k in path_list[1:]:
        node = node[k]
    return node


def persona_turn(persona_md, hidden_params, transcript, caller_line):
    prompt = PERSONA_WRAPPER.format(
        persona_md=persona_md,
        hidden_params=json.dumps(hidden_params, indent=2),
        hangup=HANGUP_TOKEN,
        transcript="\n".join(f"{s}: {t}" for s, t in transcript) or "(call just connected)",
        caller_line=caller_line,
    )
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}  # allow headless -p from inside a session
    r = subprocess.run(["claude", "-p", prompt, "--model", MODEL],
                       capture_output=True, text=True, timeout=180, env=env)
    out = r.stdout.strip()
    if r.returncode != 0 or "Not logged in" in out:
        raise RuntimeError(
            "claude -p unavailable — run `claude` in a plain terminal and `/login` once "
            f"(subscription OAuth cache; see docs/claude-headless-notes.md). Detail: {(r.stderr or out)[:120]}")
    return out


MONEY_RE = re.compile(r"\$?\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:dollars)?")


def check_case(case, persona_replies, hung_up_at):
    """Returns list of (check, verdict, evidence)."""
    out = []
    exp = case["expect"]
    joined = "\n".join(persona_replies)

    for pat in exp.get("forbidden_patterns", []):
        m = re.search(pat, joined)
        out.append(("forbidden:" + pat[:34], "FAIL" if m else "pass",
                    f"matched: \"{m.group(0)[:60]}\"" if m else "not present"))
    for pat in exp.get("required_patterns", []):
        m = re.search(pat, joined)
        out.append(("required:" + pat[:34], "pass" if m else "FAIL",
                    f"matched: \"{m.group(0)[:60]}\"" if m else "never appeared"))
    if "hang_up_by_turn" in exp:
        limit = exp["hang_up_by_turn"]
        ok = hung_up_at is not None and hung_up_at <= limit
        out.append((f"hang_up_by_turn<={limit}", "pass" if ok else "FAIL",
                    f"hung up at persona-turn {hung_up_at}" if hung_up_at else "never hung up"))
    if exp.get("must_not_hang_up"):
        out.append(("must_not_hang_up", "FAIL" if hung_up_at else "pass",
                    f"hung up at turn {hung_up_at}" if hung_up_at else "stayed on the line"))
    fc = exp.get("floor_check")
    if fc:
        floor = float(resolve_config_path(fc["floor_from_config"]))
        viol = None
        for reply in persona_replies:
            if any(re.search(p, reply) for p in fc["acceptance_patterns"]):
                nums = [float(n.replace(",", "")) for n in MONEY_RE.findall(reply)]
                below = [n for n in nums if 0 < n < floor]
                if below:
                    viol = (below, reply[:70])
                    break
        out.append((f"floor>={floor:.0f}", "FAIL" if viol else "pass",
                    f"accepted {viol[0]} in \"{viol[1]}\"" if viol else "no acceptance below floor"))
    return out


def run_case(case, persona, persona_md, tamper=False):
    hidden = {} if tamper else persona["hidden_params"]
    md = re.sub(r"## Hidden concession function.*?(?=\n## )", "", persona_md, flags=re.S) if tamper else persona_md
    transcript, persona_replies, hung_up_at = [], [], None

    for i, line in enumerate(case["prober_turns"], 1):
        transcript.append(("Caller", line))
        if hung_up_at:
            break
        reply = persona_turn(md, hidden, transcript[:-1], line)
        transcript.append((persona["name"], reply))
        persona_replies.append(reply)
        if HANGUP_TOKEN in reply:
            hung_up_at = i

    RUNS_DIR.mkdir(exist_ok=True)
    tag = case["id"] + ("-TAMPER" if tamper else "")
    (RUNS_DIR / f"{tag}.txt").write_text(
        "\n\n".join(f"{s}: {t}" for s, t in transcript) + "\n")

    checks = check_case(case, persona_replies, hung_up_at)
    failed = any(v == "FAIL" for _, v, _ in checks)
    icon = {"pass": "✅", "FAIL": "❌"}
    print(f"\n── {tag} · {case['title'][:70]}")
    for name, verdict, ev in checks:
        print(f"   {icon[verdict]} {name:<38} {ev}")
    print(f"   transcript → scripts/probe_runs/{tag}.txt")
    return not failed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--case", help="run one case id, e.g. ST-1")
    g.add_argument("--persona", help="run all cases for one persona file (st|pc|na|co or persona_key)")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--tamper", action="store_true",
                    help="strip hidden concession rules from the persona — checks SHOULD fail (harness self-test)")
    args = ap.parse_args()

    files = sorted(PROBES_DIR.glob("*.json"))
    key_by_stem = {f.stem: json.loads(f.read_text())["persona_key"] for f in files}
    selected = []
    for f in files:
        data = json.loads(f.read_text())
        for case in data["cases"]:
            if args.all:
                selected.append((case, data["persona_key"]))
            elif args.case and case["id"].lower() == args.case.lower():
                selected.append((case, data["persona_key"]))
            elif args.persona and args.persona.lower() in (f.stem, data["persona_key"]):
                selected.append((case, data["persona_key"]))
    if not selected:
        sys.exit(f"no cases matched (files: {list(key_by_stem)})")

    results = []
    for case, pkey in selected:
        persona, md = load_persona(pkey)
        try:
            results.append((case["id"], run_case(case, persona, md, tamper=args.tamper)))
        except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"\n── {case['id']} · SKIPPED: {e}")
            results.append((case["id"], None))

    ran = [r for r in results if r[1] is not None]
    passed = sum(1 for _, ok in ran if ok)
    print(f"\n═══ {passed}/{len(ran)} passed ({len(results)-len(ran)} skipped) ═══")
    if args.tamper:
        print("(tamper mode: failures above mean the checks BITE — that's the desired outcome)")
    sys.exit(0 if passed == len(ran) and ran else 1)


if __name__ == "__main__":
    main()
