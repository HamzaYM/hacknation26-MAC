"""Action-plan COPYWRITER — turns the code-computed payload (engine/action_plan.py)
into the user-facing copy blocks for the /confirm screen (prompts/action_plan.md).

Two paths, same output shape:
  * LLM: headless `claude -p` on subscription auth (docs/claude-headless-notes.md),
    with prompts/action_plan.md as the system prompt. Warm, natural prose.
  * Fallback: a deterministic template builder — used when claude is unavailable
    OR when the LLM emits a number/date not present in the input (honesty guard).

The guard is the point: PRD §7 says the copy may only rephrase computed values.
`_verbatim_ok` rejects any significant figure or date in the copy that is not in
the input payload, so a hallucinated dollar amount can never reach the user.
"""
from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache

from .config import REPO_ROOT

PROMPT_PATH = REPO_ROOT / "prompts" / "action_plan.md"

COPY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "flag_chips": {"type": "array", "items": {
            "type": "object",
            "properties": {"cpt": {"type": ["string", "null"]}, "label": {"type": "string"}},
            "required": ["label"],
        }},
        "savings_line": {"type": "string"},
        "boost_panel": {"type": "array", "items": {
            "type": "object",
            "properties": {"missing": {"type": "string"}, "copy": {"type": "string"}},
            "required": ["missing", "copy"],
        }},
        "per_call_descriptions": {"type": "array", "items": {
            "type": "object",
            "properties": {"entity": {"type": "string"}, "copy": {"type": "string"}},
            "required": ["entity", "copy"],
        }},
        "timeline_copy": {"type": "string"},
        "call_log_notes": {"type": "array", "items": {
            "type": "object",
            "properties": {"call_ref": {"type": "string"}, "copy": {"type": "string"}},
            "required": ["copy"],
        }},
        "next_step_line": {"type": "string"},
    },
    "required": ["headline", "summary", "flag_chips", "savings_line", "timeline_copy", "next_step_line"],
}


@lru_cache
def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


# ── honesty guard: every significant number/date in the copy is in the input ──
_NUM_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _sig_tokens(text: str) -> set[str]:
    """Significant tokens, canonicalized so $4,287.00 / 4287.0 / 4287 all match:
    money ($ / decimal), percentages, ISO dates, or any magnitude >= 100 (CPT
    codes, dollar sums). Small bare counts (< 100, no $/%/decimal) are free."""
    tokens: set[str] = set(_DATE_RE.findall(text))
    for raw in _NUM_RE.findall(text):
        norm = raw.replace("$", "").replace(",", "").rstrip("%")
        try:
            val = float(norm)
        except ValueError:
            continue
        if "$" in raw or "." in norm or "%" in raw or val >= 100:
            tokens.add(f"{val:.2f}")   # canonical numeric form
    return tokens


def _collect_input_tokens(node) -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        for v in node.values():
            out |= _collect_input_tokens(v)
    elif isinstance(node, list):
        for v in node:
            out |= _collect_input_tokens(v)
    elif isinstance(node, str):
        out |= _sig_tokens(node)
    elif isinstance(node, (int, float)):
        out |= _sig_tokens(str(node))
    return out


def _collect_copy_tokens(copy: dict) -> set[str]:
    out: set[str] = set()
    for v in copy.values():
        if isinstance(v, str):
            out |= _sig_tokens(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    for s in item.values():
                        if isinstance(s, str):
                            out |= _sig_tokens(s)
    return out


def _verbatim_ok(copy: dict, payload: dict) -> tuple[bool, set[str]]:
    allowed = _collect_input_tokens(payload)
    used = _collect_copy_tokens(copy)
    leaked = used - allowed
    return (not leaked), leaked


# ── deterministic fallback (always honest; every figure from the payload) ─────
def _money(x) -> str:
    return f"${x:,.2f}" if isinstance(x, (int, float)) else str(x)


def _fallback_copy(payload: dict) -> dict:
    flags = payload["flags"]
    n = len(flags)
    bal = payload["balance"]
    save = payload["savings_estimate"]
    low, high = save.get("low"), save.get("high")

    chips = []
    for f in flags:
        label = {
            "duplicate": f"Duplicate charge · {_money(f['dollar_impact'])}",
            "upcode": f"Over-coded visit · {_money(f['dollar_impact'])}",
            "unbundle": f"Unbundled labs · {_money(f['dollar_impact'])}",
            "eob_mismatch": f"Bill over EOB · {_money(f['dollar_impact'])}",
        }.get(f["type"], f"Issue · {_money(f['dollar_impact'])}")
        chips.append({"cpt": f.get("cpt"), "label": label})

    per_call = [{"entity": c["entity"], "copy": f"We'll call {c['name']} to {c['objective']}."}
                for c in payload.get("planned_calls", [])]

    boosts = [{"missing": b["missing"], "copy": f"Add your {b['missing'].replace('_', ' ')} — {b['impact_note']}."}
              for b in payload.get("boost_opportunities", [])]

    tl = payload.get("timeline", {})
    tl_bits = []
    if tl.get("fap_deadline"):
        tl_bits.append(f"you can apply for financial assistance through {tl['fap_deadline']}")
    if tl.get("credit_report_earliest"):
        tl_bits.append(f"this balance can't reach your credit report before {tl['credit_report_earliest']}")
    timeline_copy = ("It's safe to hold off on paying: " + "; ".join(tl_bits) + "."
                     if tl_bits else "Nothing here requires immediate payment.")

    savings_line = (f"Estimated savings of {_money(low)}–{_money(high)} — an estimate, not a promise."
                    if low is not None and high is not None
                    else "We'll pursue the largest reduction the evidence supports.")

    return {
        "headline": f"We found {n} billing problems on your {_money(bal)} balance.",
        "summary": (f"We reviewed the bill and flagged {n} likely errors, and lined up the calls to "
                    f"fix them. Nothing gets dialed until you approve."),
        "flag_chips": chips,
        "savings_line": savings_line,
        "boost_panel": boosts,
        "per_call_descriptions": per_call,
        "timeline_copy": timeline_copy,
        "call_log_notes": [],
        "next_step_line": "Approve the plan and we'll start the calls — every result shows up right here.",
    }


def _run_claude(payload: dict, timeout: int = 120) -> dict | None:
    prompt = (
        _system_prompt()
        + "\n\n---\n\n## INPUT (all values code-computed — use verbatim, never invent)\n\n```json\n"
        + json.dumps(payload, indent=2)
        + "\n```\n\nReturn ONLY the JSON copy blocks defined in the Output section above."
    )
    try:
        r = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(COPY_SCHEMA)],
            capture_output=True, text=True, timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
        return data.get("structured_output", data)
    except (json.JSONDecodeError, KeyError):
        return None


def generate_action_plan_copy(payload: dict, use_llm: bool = True) -> dict:
    """Copy blocks for /confirm. LLM prose when available and honest; deterministic
    fallback otherwise. Returns the copy dict plus a `_source` marker for debugging."""
    if use_llm:
        copy = _run_claude(payload)
        if copy is not None:
            ok, leaked = _verbatim_ok(copy, payload)
            if ok:
                copy["_source"] = "llm"
                return copy
            # LLM introduced an uncited figure → refuse it, fall back
            copy = _fallback_copy(payload)
            copy["_source"] = f"fallback (llm leaked {sorted(leaked)})"
            return copy
    copy = _fallback_copy(payload)
    copy["_source"] = "fallback" if use_llm else "fallback (llm disabled)"
    return copy
