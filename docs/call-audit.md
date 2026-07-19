# Call audit — all four negotiator calls, line by line

> Audited 2026-07-18 (evening): every spoken number checked against `data/seed/demo_answer_key.json`
> and the dossier, plus disclosure handling, ladder compliance, verbosity, and human-ness.
> Calls: a2a-1 `conv_3501…` (299s) · human-1 to Jay `conv_9301…` (289s) · a2a-2 `conv_8001…` (502s) ·
> human-2 to Jay `conv_1901…` (135s). Fixes marked **shipped** landed in the voice-tuning PR.

## What the audit found (ranked)

| # | Finding | Worst example | Status |
|---|---------|--------------|--------|
| 1 | Calls never closed structured: no rep name, no reference number, ended mid-hold or with a bare thank-you | a2a-1 ends "I'll continue to hold" at t=292s | **shipped** — capture name+ref BEFORE holds/transfers; speak the decline out loud |
| 2 | Fabricated date: "statement date is October twenty-sixth, two thousand twenty-three" (real: 2026-06-20; the dossier carries no date at all) | a2a-1 turn 3 | **shipped** — honesty rule now covers dates; `invented_dates` added to config forbidden list |
| 3 | Proactive AI disclosure in the opener ("I am an AI assistant…") while policy is only-if-asked — stale template was live | a2a-1 turn 1 | **shipped** — the early-disclosure template is now mode-gated (`early_mode_opening_line`) so sync drift can't re-select it. Newest call already opened competence-first |
| 4 | Verbatim repetition: full case recap replayed to each new supervisor; same hold line 11x in a row | a2a-1, a2a-2 | **shipped** — one-line re-intro after transfers; hold-line rotation; plus a deterministic engine cap (same lever+result 3x → forced next rung) |
| 5 | Benchmark rung fired without a number ("seems a bit high" — no figure) | a2a-2 | **shipped** — benchmark rung now requires get_benchmark + saying the figure, leading with the hospital's own cash price |
| 6 | Zero tool calls on the earliest call (agent narrated the ladder script instead of driving it) | a2a-1, all 74 turns | fixed earlier (4 webhook tools registered); a2a-2 and human-2 show clean tool discipline |
| 7 | Robotic acknowledgments ("I understand [restates], however…"; "thank you for looking into that" to a stonewall) | human-2 | **shipped** — added to humanizer kill-list; proportional reactions instead |
| 8 | Line items led with the CPT code, inverting TREATMENT-DATE-CODE-COST | a2a-2 | **shipped** — explicit YES/NO example in verbalization guide |
| 9 | Dead air into tool lookups, then instantly fluent | a2a-2 | **shipped** — filler line required before any lookup, promoted into the load-bearing prompt |
| 10 | Soft permission-seeking framing ("see if there are any options") cedes the negotiable frame | a2a-1 | **shipped** — banned paraphrase list broadened |
| 11 | Verbose front-loaded openers | human-2 | fixed earlier (hard turn cap + short opener) — verify on the next live call |

## What's working — do not break these
- Numbers honesty once tools are wired: every figure in a2a-2 and human-2 traces to the dossier or get_benchmark.
- Floor/anchor/target discipline: offered exactly $657 then $876, never crossed the $1,700 floor under pressure.
- Stonewall recognition generalizes past the config's literal trigger strings ("That's our standard charge" was caught).
- Proportional warmth on real concessions ("Oh, that's great — thank you") and calm under strain (a dismissive "bro" didn't rattle it).
- Digit-by-digit CPT verbalization and un-rounded exact dollar figures.

## Verify on the next test call
1. Opener is two short beats + "Got a minute?" (≤25 words).
2. A benchmark moment includes a real figure, cash price first.
3. Call ends with rep name + reference number banked before any transfer.
4. Hold lines vary; no case recap after a transfer.
5. War Room streams live (attribution fix from PR #45).
