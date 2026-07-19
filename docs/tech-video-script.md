# Tech Video · 60-Second Script (stack, architecture, implementation) · Owner: Kar Shin

Submission slot: **Tech Video (max 60 sec)**, "Technical explanation: cover your stack,
architecture, and implementation."

Visual: screen-record **`/tech-video`** on hagglfor.me (or `npm run dev` then
`http://localhost:3000/tech-video`). The page is a 6-slide deck timed to this script.
Press **Space** to start the 60-second auto-run (slides advance on the beat marks, every
element animates in), or use ←/→ to drive it manually. 1280×800 stage, same recording
setup as the pitch deck.

The angle is straight, not confessional: the system is mostly deterministic code with an
LLM bolted on only where a human voice is needed, and the whole thing is live at
hagglfor.me. Read it out loud once before you record. If a line doesn't sound like
something you'd actually say, change it. Word counts are a ceiling at ~150 wpm, not a
target. Slower, with pauses, always reads better.

---

### 0:00 to 0:09 · Slide 1 · "the whole thing is live"
**[SCREEN]** Five-box service strip: Next.js, FastAPI, Supabase, ElevenLabs, Twilio. Chip reads "live at hagglfor.me".
**[V]** "It's all live at hagglfor dot me right now. We use an LLM only where a voice is
needed, and keep everything else plain code." *(~24 words / 9s)*

### 0:09 to 0:22 · Slide 2 · "a. One negotiation turn" (diagram)
**[SCREEN]** Editorial flow diagram: rep speaks → the LLM (the mouth) → `report_lever_result()` → the deterministic `advance()` gate (floor, plan math, repetition, coverage) → allowed or forced move. Tagline: "The AI never picks the price. Code does."
**[V]** "Here's one turn. The rep stonewalls, the model calls a tool, and a deterministic
gate decides what happens next. It checks the floor, the plan math, repetition, coverage.
The model never picks the price. Code does." *(~34 words / 13s)*

### 0:22 to 0:35 · Slide 3 · "the code holds the line"
**[SCREEN]** Six guardrail cards: numbers only through tools, the impossible offer, plan math server-side, injection refused, never denies the AI, every call audited.
**[V]** "The model is on a short leash. It can only say numbers that come through a tool.
An offer above what the patient can pay is impossible. And after every call, code re-reads
every number it spoke." *(~34 words / 13s)*

### 0:35 to 0:45 · Slide 4 · "b. Runtime topology" (diagram)
**[SCREEN]** Editorial topology: the screen path (browser → Next.js → FastAPI → Supabase → War Room) and the call path (FastAPI → ElevenLabs → Twilio → a real phone), fed by an 881,668-row chargemaster (MGH, Brigham & Women's, Newton-Wellesley) and real CMS Medicare rates.
**[V]** "It's all real infrastructure. Next dot js and FastAPI run the app, calls go out
through ElevenLabs and Twilio, and every price it cites comes from a real chargemaster and
real Medicare rates." *(~28 words / 10s)*

### 0:45 to 0:55 · Slide 5 · "new market? one file"
**[SCREEN]** `medical_bills.yaml` next to a proof panel: 9 scenarios (sc01 to sc09), answer keys computed by the engine, `generate.py --check` byte-stable.
**[V]** "Want a new market? That's one config file, not a rewrite. The engine doesn't know
it's medicine. Nine scenarios prove it, every answer key computed by code." *(~27 words / 10s)*

### 0:55 to 1:00 · Slide 6 · Close (dark card)
**[SCREEN]** "Code decides what's true. The model decides how to say it." Wordmark, hagglfor.me.
**[V]** "Code decides what's true. The model just decides how to say it." *(~12 words / 5s)*

---

## Why this covers the brief

| What the judges are told to look for | Where it lands |
|---|---|
| Stack | 0:00 to 0:09, all five services named, and it's live |
| Architecture | Slide 2 (one turn) and Slide 4 (runtime topology) |
| Implementation | Slide 3 (guardrails) and Slide 5 (config, not code) |
| Real negotiation, price moves for a reason | Slide 2, the `advance()` gate is the mechanism, not a script |
| An LLM used sparingly | Slides 1 to 3, the model is the mouth, the code is the brain |
| Guardrails that hold | Slide 3, tool-gated numbers, impossible over-offers, injection refused, never denies the AI, post-call audit |
| Grounded in real data | Slide 4, 881,668-row chargemaster (3 Boston hospitals) plus real CMS PFS/OPPS/CLFS rates |
| Config, not code | Slide 5, one YAML per market, 9 scenarios with code-computed keys |
| It actually ships | Slides 1 and 6, live and hosted at hagglfor.me right now |

## Production notes
- Record at 1280×800. The stage scales itself, same as the pitch deck.
- Space plays the full 60 seconds. R resets to the start. Arrows step manually.
- Read it like you're explaining it to someone at the table next to you, not presenting
  to a room. Slower than you think, with real pauses.
- If a take runs long, the first thing to cut is the last sentence of slide 3 or slide 4,
  they're the least load-bearing.
