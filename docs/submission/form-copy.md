# Hack-Nation submission: form copy (paste-ready)

Deadline: 9:00 AM ET today. Every field below is drafted to paste directly.
Numbers were verified against the repo (pitch.html, README, architecture.md, the
engine code, and a `pytest --collect-only` run). Voice guide followed: no
em-dashes, plain sentences.

---

## Project Title

**Haggl**

Tagline: The AI advocate that calls your hospital and negotiates the bill down.

(If the form has a single title field, use: `Haggl: the AI advocate that calls
your hospital and negotiates the bill down`.)

---

## Short Description (1-2 sentences)

Haggl reads your hospital bill, finds the billing errors and the laws on your
side, then places a real phone call to the billing office and negotiates the
balance down on a live call. In our demo it takes a $4,287 ER bill to $1,650
settled, a 62% reduction, with every number it speaks computed by code and gated
through a tool so it cannot bluff.

---

## 1. Problem & Challenge

Medical bills in the US are wrong often and priced almost at random. Americans
hold $220B in medical debt today (KFF, 2025). Private insurers pay 254% of
Medicare rates for the same care (RAND, 2024), hospitals mark up 3.4x over
Medicare cost on average and up to 12.6x at outliers (Bai & Anderson, Health
Affairs 2015), and an estimated 49-80% of bills contain errors. The person who
could push back, the patient, is the one least equipped to. They do not know the
fair price, cannot spot a duplicate charge or an upcode, do not know which
statute caps what they owe, and dread the phone call. So they pay. The challenge
is not writing a chatbot that gives advice. It is building an agent trustworthy
enough to speak on someone's behalf on a recorded phone call, cite real prices
and real law, and never invent a number, because a single hallucinated figure on
that call destroys the patient's credibility and the whole case.

---

## 2. Target Audience

The direct user is any US patient holding a hospital bill they suspect is wrong
or unaffordable: the surprise ER balance, the out-of-network anesthesia charge,
the bill already sold to collections. Our three demo personas map to the real
routes. Maya has a $4,287 ER balance with seeded duplicate, upcode, unbundle, and
EOB errors. Dan has $2,140 sold to a collections agency. Nina has a $3,120
out-of-network anesthesia balance bill covered by the No Surprises Act. These are
the people who today either overpay in silence or spend hours on hold with no
idea what a fair number even is. Downstream, the same engine serves patient
advocates and financial-counseling nonprofits who make these calls professionally
and are bottlenecked by call volume. The design is deliberately not medical-only:
verticals are config, so the same state machine retargets to any negotiation
where a consumer faces an information-asymmetric counterparty. A moving-quotes
vertical stub ships alongside the medical one to prove it.

---

## 3. Solution & Core Features

Haggl runs the full loop end to end. You upload your bill and its EOB. OpenAI
vision extracts every line, and the deterministic flag engine reconciles the
parse against the case file and detects duplicates, upcodes, unbundled panels,
EOB mismatches, and markups. It prices every code against real hospital
chargemaster data and CMS Medicare rates, builds a strategy dossier with an
anchor, target, and floor, then places a real phone call through ElevenLabs
Agents and Twilio and negotiates. Core features: a live War Room that streams
every call event (transcript, tool call, quote, escalation) over Supabase
Realtime as it happens; a case file with the archived call audio and outcome; a
recorded patient authorization the agent presents when a rep challenges identity;
a coded negotiation ladder that escalates to a supervisor when stonewalled; and a
post-call honesty audit that checks every spoken number. Pricing is aligned to
the user: 25% of what we save you, capped at $2,000 per bill, nothing upfront,
and nothing if we do not save you anything.

---

## 4. USP

The LLM is the mouth, not the brain-stem. Every negotiation decision, every
threshold, every number, and every legal claim is computed in deterministic
server-side code and served to the voice model through a tool. The model only
decides how to say it. This is what makes an agent you can actually put on a
recorded call. The numbers it may speak are tool-gated to two sources, so it
cannot bluff a price. The reduction percentage is computed in code, never by the
model. Any offer above the case floor is rejected before it can be spoken.
Settling above target fires a human-confirmation event in the War Room. The
disclosure rule `never_deny_ai` is absolute, so the agent confirms it is an AI the
instant it is asked. Honesty is then verified, not asserted: a deterministic eval
gate checks disclosure timing and every spoken number after each call. Competing
tools hand you a script to read or a letter to mail. Haggl makes the call, and it
is structurally incapable of lying on it.

---

## 5. Implementation & Technology

Next.js frontend, FastAPI backend, Supabase (Postgres, Storage, Realtime),
ElevenLabs Agents for the voice loop, Twilio for the PSTN transport, and OpenAI
for offline vision and text. Every call is a real phone call through ElevenLabs'
native Twilio integration, so there is no separate demo audio stack to distrust.
The seams between modules are frozen JSON Schemas in `contracts/` (job_spec,
benchmark_row, strategy_dossier, call_outcome), so four people built against them
and the pieces met in the middle. The negotiation policy is a LadderStateMachine
walking a config-defined ladder. Mid-call the agent reports what happened through
webhook tools and the server answers with the required next move. Everything
vertical-specific lives in one YAML per market, so retargeting the system is
writing a config file plus benchmark data, not new code. Real data is gated by
reconciliation: an 881,668-row chargemaster from three Boston hospitals plus CMS
PFS, OPPS, and CLFS Medicare rates feed a pipeline whose output must pass a check
against a single answer key before anyone integrates it. 349 tests pass.

---

## 6. Results & Impact

The product is live and hosted at hagglfor.me and makes real phone calls. In the
flagship demo it takes Maya's $4,287 ER balance to $1,650 settled, a 62%
reduction, and every step is caused by data and tools rather than a script. The
duplicate charge comes off first ($4,287 to $3,875), the agent anchors on the
$438 Medicare total and the hospital's own posted $2,633.25 cash price, the rep
counters $2,400, and it settles at $1,650. Behind the demo: 349 passing tests, an
881,668-row real chargemaster from three Boston hospitals, real CMS Medicare
rates, nine generated scenarios each with a code-computed answer key, and a
post-call honesty audit. Two live-call failures became guardrails within the hour
they appeared. An agent that agreed to a $150 x 55-month plan totaling $8,250 on a
$3,875 balance now hits a server-side plan-total ceiling that rejects it out loud
in dollars. The impact claim is narrow and real: a patient who would have paid
$4,287 pays $1,650, and the agent never said anything untrue to get there.

---

## Most fun moment (3 candidates, recommendation below)

### Candidate A: the $8,250 chaos call (RECOMMENDED)

We handed the agent to a friend and told him to be a nightmare counterparty. He
talked it into a payment plan: $150 a month for 55 months. The agent phrased the
acceptance beautifully, warm, professional, completely reasonable sounding. Then
someone did the multiplication. $150 times 55 is $8,250, on a balance of $3,875.
The agent had agreed, in a lovely voice, to more than double the bill. Within the
hour we shipped a server-side plan-total guardrail. The engine now multiplies any
plan out, folds in interest, compares the total to the case floor, and rejects it
out loud, converting monthly-times-months back into real dollars so the agent
counters instead of charming its way into a terrible deal. It is the whole thesis
of the project in one bug: a fluent model will happily say something insane, so
the math has to live in code.

### Candidate B: the agent asked for the bill it already had

Mid-call, our agent politely asked the hospital to mail an itemized bill, the
exact document Haggl had already parsed and built the entire case from. We were
arguing from a bill in one hand while asking for it with the other. We fixed it
with a records-alignment rule: the agent now knows it already holds the itemized
bill and confirms the records instead of requesting them.

### Candidate C: four rejections and one missing word

Our first sync between our engine and ElevenLabs failed four times in a row. The
agent config kept getting rejected and the error was unhelpful. We finally found
it: ElevenLabs requires a description on every single node of a tool's parameter
schema, including the items of an array, not only the top-level fields. One
missing description on an array's element type, four failed syncs. There is a
comment in the code now so no one loses that hour again.

### Recommendation

Ship **Candidate A**. It is the most memorable, the math is genuinely funny, and
it demonstrates the core architecture claim, deterministic guardrails around a
fluent model, better than anything else we could tell you.

---

## Additional Information (optional field): links block

- Live site: https://hagglfor.me
- Pitch deck: https://hagglfor.me/pitch-sf-2026
- Tech tour video: https://hagglfor.me/tech-video
- Repo: https://github.com/HamzaYM/hacknation26-MAC

---

## Live Project URL

https://hagglfor.me

## GitHub

https://github.com/HamzaYM/hacknation26-MAC

---

## Technologies / Tags

**Core stack:** Next.js, FastAPI, Supabase, ElevenLabs, Twilio, OpenAI, Python,
TypeScript

**Additional tags:** voice-agents, negotiation, medical-bills,
deterministic-guardrails, real-phone-calls

---

## Team

- Hamza Malik (product and engine)
- Susy Liu (UX)
- Jay Vachhani (data)
- Kar Shin Cheo (personas and video)
