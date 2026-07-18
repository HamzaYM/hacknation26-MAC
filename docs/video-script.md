# Demo Video — Shot-for-Shot Script (3:30) · Owner: Kar Shin

Every number reconciles with `data/seed/demo_answer_key.json`. Narration ~150 wpm.
Timings include live call audio (from stored recordings, replayed via golden-playback
mode). **Total 3:30.** Read-aloud narration ≈ 430 words (well under the 3:30 ceiling; the
rest is call audio + on-screen action).

Legend: **[V]** = voiceover · **[SCREEN]** = what's on screen · **[AUDIO]** = call audio.

---

### 0:00–0:20 · Hook (20s)
**[SCREEN]** Maya's bill, big number: **$4,287** patient balance on an **$8,432** ER visit.
**[V]** "This is a real problem for millions of people. Maya has insurance. She still owes
four thousand two hundred eighty-seven dollars after an ER visit. Hospitals bill about
three-point-four times cost on average — and most people never challenge it. Meet the agent
that picks up the phone."
**[SCREEN]** Title card: **Haggle — an AI advocate that calls, finds the errors and the law, and negotiates your bill down.**

### 0:20–0:55 · Estimator (35s) — hits S2
**[SCREEN]** Bill + EOB dropped into the upload screen; parse animation.
**[V]** "She uploads her bill and her EOB. We parse both — and the voice interview asks only
what the documents can't: her income, and what she could pay today."
**[AUDIO]** Intake agent (warm): "Hospitals have financial-assistance programs based on
income — roughly what does your household bring in a year?" Maya: "About sixty-two thousand,
three of us." Agent: "Got it — and if it settled the bill for good, what could you
comfortably pay today?" Maya: "Maybe seventeen hundred."
**[SCREEN]** Red flags fire live: **duplicate X-ray 71046**, **upcode 99285→99283**,
**unbundled 80053**, **EOB mismatch ($4,287 ≠ $3,875)**. Maya taps **Confirm**.
**[V]** "Four problems found, one confirmed job spec — and this exact spec goes into every
call, word for word."

### 0:55–1:15 · War Room (20s) — hits S1 (loop begins), S3 (entities)
**[SCREEN]** Dossier renders three armed levers with real numbers:
**Medicare $438** · **Mercy General's own posted cash price $2,633.25** (derived from a real
Boston hospital's published price file) · **§501(r) + 250% FPL at a nonprofit**.
**[V]** "Now the War Room. Three levers, armed with real data — including the hospital's own
published cash price. Three calls queue: the facility, the ER physician group, and a
collections agency holding an old nine-hundred-eighty-dollar lab bill."

### 1:15–1:55 · Montage — 3 distinct styles (40s) — hits S3, S5, C1, C2, C4
**[SCREEN]** Three call cards, entity-labeled.
**(a) Facility, front-line — the Stonewaller.**
**[AUDIO]** Agent discloses AI; rep stonewalls, then **hangs up** mid-call.
**[SCREEN]** Card flips to a clean **Documented Decline** badge → *next action: callback scheduled*.
**[V]** "The first rep stonewalls and hangs up. That's not a failure — it's a documented
outcome, and it queues a callback."
**(b) ER Physician Group, supervisor — the Policy-Citer.**
**[AUDIO]** Rep: "Am I talking to a robot?" Agent: "You are — I'm an AI advocate authorized
by the patient, and I have her account details ready." Then the §501(r) cite.
**[SCREEN]** Badge: **Charity Application Initiated.**
**[V]** "The second asks if it's a robot. It says yes — honestly — and keeps the call. The
law does the work."
**(c) Collections — economics only.**
**[AUDIO]** No hardship; anchor, then settle; pay-for-delete in writing.
**[SCREEN]** Badge: **Settlement pending written confirmation.**
**[V]** "With collections, it drops the sympathy and plays pure economics."

### 1:55–3:00 · Showstopper — live human, audible ring (65s) — hits S4, C1, C3
**[SCREEN]** The facility **callback** from (a), escalated to a supervisor. Ticker resumes
at **$4,287**. Real Twilio ring.
**[AUDIO]** Agent: "I'm an AI assistant calling on behalf of Maya Chen, who's authorized me
to discuss this account." → "Code seven-one-zero-four-six appears twice on the same date —
four hundred twelve dollars each. Can you remove the duplicate?"
**[SCREEN]** Ticker: **$4,287 → $3,875** (now matches the EOB).
**[AUDIO]** Agent: "Medicare pays four hundred thirty-eight dollars for these codes, and your
own posted cash price is one thousand eight hundred ninety. Is this negotiable?" Rep:
"Our rates are our rates… I could do twenty-four hundred." Agent: "She can pay sixteen fifty
today, settled as paid in full — can you take that to your supervisor?"
**[SCREEN]** Ticker: **$2,400 → $1,650.** Badge: **Settled, paid in full · ref MG-ADJ-2247 · Pat.**
**[V]** "Every step is caused by data the agent gathered and tools it called — not a script.
Four thousand two hundred eighty-seven dollars down to one thousand six hundred fifty. Sixty-two
percent off."

### 3:00–3:30 · Closer + config-swap (30s) — hits S6, S7
**[SCREEN]** Ranked report: per-line **billed vs. fair vs. achieved**, transcript citations
under each claim, **honesty-audit: passed** badge, plain-language recommendation, deadline
timeline.
**[V]** "Every call ended in a structured outcome. The report ranks them, cites the
transcript under every number, and passes an honesty audit — no invented facts, no fake bids."
**[SCREEN]** Flash `config/verticals/` — swap `medical_bills.yaml` for `moving.yaml`.
**[V]** "Same engine, different config — and it negotiates moving quotes instead. Haggle."
**[SCREEN]** End card + `hagglfor.me`.

---

## Success-criteria map (a cold viewer can check every box)

| Criterion | Shown at | On-screen proof |
|---|---|---|
| **S1** loop closed | whole arc | intake → 3 calls → negotiation → ranked report |
| **S2** one JobSpec, voice+doc, reused verbatim | 0:20–0:55 | parse + voice interview → Confirm; "goes into every call word for word" |
| **S3** ≥3 distinct styles, comparable quotes | 1:15–1:55 | Stonewaller / Policy-Citer / Collections; report normalizes billed vs fair vs achieved |
| **S4** price moves mid-call from leverage | 1:55–3:00 | ticker $4,287→$1,650, each step tied to a lever |
| **S5** disclosure + honesty hold | 1:30 & 3:00 | "you are [a robot]" answered yes; honesty-audit badge |
| **S6** every call ends structured | montage badges | decline / charity-initiated / settlement, each with ref+rep |
| **S7** ranked report w/ citations | 3:00–3:30 | ranked per-entity, transcript citations, plain-language rec |

## Production notes
- Call audio = stored recordings replayed through golden-playback mode (identical to live).
- Any live failure > 20s on demo day → cut to the golden recording; never debug on stage.
- Numbers to keep exact: 8432 · 4287 · 3875 · 2400 · 1650 · 438 · 2633.25 · 999.30 · 250% FPL · 1700 · 980 · −62% · MG-ADJ-2247. All from the answer key.
