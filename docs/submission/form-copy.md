# Hack-Nation submission: form copy (paste-ready)

Deadline: 9:00 AM ET today. Every field is one paragraph on one line so it pastes clean. Numbers verified against the repo (pitch.html, README, architecture.md, the engine code, the test suite).

---

## Project Title

**Haggl**

Tagline: The AI advocate that calls your hospital and negotiates the bill down.

(Single title field version: `Haggl: the AI advocate that calls your hospital and negotiates the bill down`)

---

## Short Description (1-2 sentences)

Haggl reads your hospital bill, finds the billing errors and the laws on your side, then places a real phone call to the billing office and negotiates the balance down live. In our demo it takes a $4,287 ER bill to $1,650 settled, a 62% reduction, and every number it speaks is computed by code and gated through a tool so it cannot bluff.

---

## 1. Problem & Challenge

Medical bills in the US are wrong often and priced almost at random. Americans hold $220B in medical debt (KFF, 2025). Private insurers pay 254% of Medicare rates for the same care (RAND, 2024), hospitals mark up 3.4x over Medicare cost on average and up to 12.6x at outliers (Bai & Anderson, Health Affairs 2015), and an estimated 49-80% of bills contain errors. The patient is the one person positioned to push back and the one least equipped to: they do not know the fair price, cannot spot a duplicate charge or an upcode, do not know which statute caps what they owe, and dread the phone call. So they pay. A chatbot that hands out advice does not change any of that. The hard part is an agent trustworthy enough to speak on someone's behalf on a recorded phone call, cite real prices and real law, and never invent a number, because one hallucinated figure on that call sinks the patient's credibility and the whole case.

---

## 2. Target Audience

The direct user is any US patient holding a hospital bill they suspect is wrong or unaffordable: the surprise ER balance, the out-of-network anesthesia charge, the bill already sold to collections. Our three demo accounts map to those routes. Maya has a $4,287 ER balance carrying duplicate, upcode, unbundle, and EOB errors. Dan has $2,140 sold to a collections agency. Nina has a $3,120 out-of-network anesthesia balance bill covered by the No Surprises Act. These are the people who today overpay in silence or spend hours on hold with no idea what a fair number is. And negotiating is a skill most people never get to practice: the shy, the non-assertive, anyone whose accent gets them talked over on the phone either avoids these calls or loses them. Haggl puts the same firm, fluent advocate on the line for them that a confident negotiator already is for themselves, an edge they would not otherwise have. Downstream, the same engine serves patient advocates and financial-counseling nonprofits who make these calls professionally and are bottlenecked by call volume. Verticals are config, so the same state machine retargets to any negotiation where a consumer faces a counterparty who knows the prices and the rules better than they do. A moving-quotes vertical stub ships alongside the medical one to prove it.

---

## 3. Solution & Core Features

Haggl runs the loop end to end. You upload the bill and the EOB. OpenAI vision extracts every line, and the deterministic flag engine reconciles the parse against the case file and catches duplicates, upcodes, unbundled panels, EOB mismatches, and markups. It prices every code against real hospital chargemaster data and CMS Medicare rates, builds a strategy dossier with an anchor, a target, and a floor, then places a real phone call through ElevenLabs Agents and Twilio and negotiates. Core features: a live War Room that streams every call event (transcript, tool call, price quote, escalation) over Supabase Realtime as it happens; a case file with the archived call audio, reference numbers, and outcomes; a recorded patient authorization the agent presents when a rep challenges its standing; a coded negotiation ladder that escalates to a supervisor when stonewalled; and a post-call honesty audit that re-reads every number the agent spoke. Pricing sits on the user's side of the table: 25% of what we save you, capped at $2,000 per bill, nothing upfront, nothing if we save you nothing.

---

## 4. USP

The LLM is the mouth, not the brain-stem. Every negotiation decision, every threshold, every number, and every legal claim is computed in deterministic server-side code and handed to the voice model through a tool; the model only decides how to say it. That is what lets you put an agent on a recorded call. The numbers it may speak are tool-gated to the case facts and the counterparty's own stated figures, so it cannot bluff a price. Any offer above the case floor is rejected before it can be spoken, payment plans are multiplied out server-side with interest included, and settling above target fires a human-confirmation event in the War Room. The disclosure rule never_deny_ai is absolute: asked whether it is an AI, it says yes and keeps negotiating. After every call a deterministic audit checks disclosure timing and every spoken number against the case's allowed set. The tactics are researched, not improvised: the agent's playbook encodes negotiation psychology, from the pause before a concession to the face-saving exit to the empathy clause that lets an escalation land soft. Competing tools hand you a script to read or a letter to mail. Haggl makes the call.

---

## 5. Implementation & Technology

Next.js frontend, FastAPI backend, Supabase (Postgres, Storage, Realtime), ElevenLabs Agents for the voice loop, Twilio for the PSTN transport, and OpenAI for offline vision and text. Every call is a real phone call through ElevenLabs' native Twilio integration, so there is no separate demo audio stack. The seams between modules are frozen JSON Schemas in contracts/ (job_spec, benchmark_row, strategy_dossier, call_outcome), which let four people build against them and meet in the middle. The negotiation policy is a ladder state machine walking rungs defined in config. Mid-call the agent reports each exchange through webhook tools and the server answers with the required next move. Everything vertical-specific sits in one YAML per market, so retargeting the system means writing a config file and benchmark data, not new code. Real data is gated by reconciliation: an 881,668-row chargemaster from three Boston hospitals plus CMS PFS, OPPS, and CLFS Medicare rates feed a pipeline whose output must match a committed answer key before anyone integrates it. 351 tests pass.

---

## 6. Results & Impact

The product is live at hagglfor.me and makes real phone calls. The flagship negotiation happened on a real line: our negotiator called our hospital-supervisor counterparty agent over the PSTN, got the duplicate charge adjusted ($4,287 to $3,875), anchored on the $438 Medicare benchmark and the hospital's own posted $2,633.25 cash price, took the $2,400 counter, and settled at $1,650 paid in full with reference MG-ADJ-2247 read back on the call. That call is archived in the case file with audio, and the War Room ticker moved on every concession as it happened. Behind it: 351 passing tests, an 881,668-row real chargemaster from three Boston hospitals, real CMS Medicare rates, nine generated scenarios each with a code-computed answer key, and a post-call honesty audit. Live-call failures became guardrails within the hour they appeared; the agent that once accepted a $150 x 55-month plan totaling $8,250 on a $3,875 balance now hits a server-side plan-total ceiling that rejects the math out loud in dollars. The impact claim stays narrow and checkable: a patient who would have paid $4,287 pays $1,650, and the agent never said anything untrue to get there.

---

## Most fun moment (3 candidates, recommendation below)

### Candidate A: the $8,250 chaos call (RECOMMENDED)

We handed the agent to a friend and told him to be a nightmare counterparty. He talked it into a payment plan: $150 a month for 55 months. The agent phrased the acceptance beautifully, warm, professional, completely reasonable sounding. Then someone did the multiplication. $150 times 55 is $8,250, on a balance of $3,875. The agent had agreed, in a lovely voice, to more than double the bill. Within the hour we shipped a server-side plan-total guardrail: the engine multiplies any plan out, folds in interest, compares the total to the case floor, and rejects it out loud in real dollars so the agent counters instead of charming its way into a terrible deal. It is the whole thesis of the project in one bug. A fluent model will happily say something insane, so the math has to live in code.

### Candidate B: the agent asked for the bill it already had

Mid-call, our agent politely asked the hospital to mail an itemized bill, the exact document Haggl had already parsed and built the entire case from. We were arguing from a bill in one hand while asking for it with the other. We fixed it with a records-alignment rule: the agent now knows it already holds the itemized bill and confirms the records instead of requesting them.

### Candidate C: four rejections and one missing word

Our first sync between our engine and ElevenLabs failed four times in a row, and the error message never said why. We finally found it: ElevenLabs requires a description on every single node of a tool's parameter schema, including the items of an array, not only the top-level fields. One missing description on an array's element type, four failed syncs. There is a comment in the code now so no one loses that hour again.

### Recommendation

Ship **Candidate A**. It is the most memorable, the math is genuinely funny, and it shows the core architecture claim, deterministic guardrails around a fluent model, better than anything else we could tell you.

---

## Additional Information (optional field): links block

- Live site: https://hagglfor.me
- Pitch deck: https://hagglfor.me/pitch-sf-2026
- Technical architecture: https://hagglfor.me/technical-architecture
- Tech tour: https://hagglfor.me/tech-video
- Repo: https://github.com/HamzaYM/hacknation26-MAC

---

## Live Project URL

https://hagglfor.me

## GitHub

https://github.com/HamzaYM/hacknation26-MAC

---

## Technologies / Tags

**Core stack:** Next.js, FastAPI, Supabase, ElevenLabs, Twilio, OpenAI, Python, TypeScript

**Additional tags:** voice-agents, negotiation, medical-bills, deterministic-guardrails, real-phone-calls

---

## Team

- Hamza Malik (product and engine)
- Susy Liu (UX)
- Jay Vachhani (data)
- Kar Shin Cheo (personas and video)
