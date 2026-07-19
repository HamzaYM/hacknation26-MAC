"""Deterministic parser for the voice intake agent's transcript.

The intake ElevenLabs agent asks the four things the documents can't answer —
what the patient can put down today, the most they can manage monthly, and their
household income + size. This turns that transcript into the JobSpec's financial
fields, conservatively: a field is only emitted when BOTH the agent's question is
confidently classified AND the following patient turn carries a number. Anything
ambiguous is left unset (the fixture value stands).

Keys are the JobSpec's internal names so they overlay cleanly onto the fixture
profile (fixtures.py): lump_sum_available, max_monthly_payment, household_income,
household_size.
"""
from __future__ import annotations

import re

# Question → field. Checked most-distinctive first so "a month" beats "a year"
# etc. Order matters: household size before the dollar questions (it's a count,
# not a dollar amount), then lump-sum, monthly, income.
_SIZE_CUES = ("how many people", "household size", "family size", "people in your",
              "people live", "how many are in", "size of your household")
_LUMP_CUES = ("put down today", "put down", "lump sum", "lump-sum", "up front",
              "upfront", "pay today", "one payment", "all at once", "right now")
_MONTHLY_CUES = ("comfortably pay", "each month", "per month", "a month",
                 "every month", "monthly", "month toward", "month towards")
_INCOME_CUES = ("household income", "make a year", "annual income", "a year",
                "per year", "yearly", "annually", "gross income", "income")

_NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


def _classify(question: str) -> str | None:
    q = question.lower()
    if any(c in q for c in _SIZE_CUES):
        return "household_size"
    if any(c in q for c in _LUMP_CUES):
        return "lump_sum_available"
    if any(c in q for c in _MONTHLY_CUES):
        return "max_monthly_payment"
    if any(c in q for c in _INCOME_CUES):
        return "household_income"
    return None


def _words_to_number(text: str) -> float | None:
    """Spoken cardinal → number ('two thousand five hundred' → 2500). Returns
    None when no number words are present."""
    tokens = re.findall(r"[a-z]+", text.lower())
    total, current, seen = 0.0, 0.0, False
    for tok in tokens:
        if tok in _NUM_WORDS:
            current += _NUM_WORDS[tok]
            seen = True
        elif tok == "hundred":
            current = (current or 1) * 100
            seen = True
        elif tok in ("thousand", "grand", "k"):
            total += (current or 1) * 1000
            current = 0.0
            seen = True
        elif tok in ("and", "a"):
            continue
        else:
            # a non-number word breaks the run only if we've started one
            if seen and current:
                total += current
                current = 0.0
    total += current
    return total if seen and total else None


def _to_money(text: str) -> float | None:
    """The dollar amount in a patient turn, or None. Digit forms first
    ($2,500 / 2500 / 2,500.00 / '2 thousand'), then spoken words."""
    digits = re.findall(r"\$?\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)", text)
    if digits:
        raw = digits[-1]
        val = float(raw.replace(",", ""))
        tail = text[text.rfind(raw) + len(raw):][:16].lower()
        if "thousand" in tail or re.search(r"\bk\b", tail):
            val *= 1000
        elif "hundred" in tail:
            val *= 100
        return val
    return _words_to_number(text)


def _to_int(text: str) -> int | None:
    """A small integer (household size), from digits or number words."""
    m = re.search(r"\b(\d{1,2})\b", text)
    if m:
        return int(m.group(1))
    n = _words_to_number(text)
    return int(n) if n is not None and n == int(n) else None


def _is_agent(turn: dict) -> bool:
    role = (turn.get("role") or turn.get("speaker") or "").lower()
    return role == "agent"


def _text_of(turn: dict) -> str:
    return (turn.get("message") or turn.get("text") or "").strip()


def parse_financial_answers(transcript: list[dict]) -> dict:
    """Walk the transcript in order; attribute each patient answer to the field
    the preceding agent question asked about. Last confident value per field
    wins. Returns only the fields matched with a number."""
    result: dict = {}
    pending: str | None = None
    for turn in transcript or []:
        text = _text_of(turn)
        if not text:
            continue
        if _is_agent(turn):
            pending = _classify(text)          # may be None → ignore the reply
            continue
        if pending is None:
            continue
        if pending == "household_size":
            value = _to_int(text)
        else:
            value = _to_money(text)
        if value is not None and value > 0:
            result[pending] = value
    return result
