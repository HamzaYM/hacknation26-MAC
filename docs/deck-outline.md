# Pitch Deck — Outline (~8 slides) · Owner: Kar Shin

Reuse diagrams from `The Negotiator - Visual Brief.dc.html` where noted. Every number
reconciles with `data/seed/demo_answer_key.json` and PRD §2. Covers the PRD §15 mandated
slides: **code-vs-LLM matrix, honesty/disclosure design, config-swap vision.**

---

### 1 · Title
**Haggle — an AI advocate that calls, compares, and haggles your medical bills down.**
Hack-Nation 6th Global AI Hackathon · Challenge 01 (ElevenLabs). Team: Suzy · J · Hamza · Kar Shin.
One-line: *reads your bill + EOB, finds the errors and the law on your side, and negotiates the price down on a live call.*

### 2 · The problem (provable pain)
- Maya: insured, still owes **$4,287** after an **$8,432** ER visit.
- Hospital charges avg **3.4× cost** (Bai/Anderson); commercial payers pay **254% of Medicare** (RAND).
- **64%** of Americans have never challenged a bill — yet most who do, win (**~78%** get a reduction, AKASA). *[directional — label on slide]*
- The gap isn't information; it's the phone calls nobody has time for. Software now makes them.
- *Visual: the $1,158–$6,506 spread framing from the Visual Brief, adapted to the medical bill.*

### 3 · What we built — the three modules
Estimator → Caller → Closer, one closed loop. *Visual: the architecture flow from Visual Brief §6 / PRD §6 mermaid (Next.js · FastAPI · Supabase · ElevenLabs+Twilio · OpenAI).*
- **Estimator:** bill+EOB parsed + ElevenLabs voice interview → one confirmed JobSpec, reused verbatim.
- **Caller:** real Twilio calls vs. distinct counterparties; structured, comparable quotes.
- **Closer:** deterministic negotiation ladder + ranked, transcript-cited report.

### 4 · The three-lever negotiation stack
Reuse the Visual Brief's three-lever diagram: **errors → statutory rights → price benchmarking.**
- Grounded in **real data**: Medicare + **the hospital's own published price-transparency file** (Mercy's posted cash price **$1,890** for Maya's codes).
- Combined levers routinely cut **30–70%**; charity care **50–100%**. *[directional — labeled]*

### 5 · Code vs. LLM — the honesty architecture (MANDATED)
Reuse/adapt PRD §7 matrix. **The thesis:** anything with a number, threshold, or legal claim
is **computed in code** and injected; the LLM is the mouth, not the brain-stem.
- Benchmarks, bands, red-flag detection, the negotiation ladder, concession floors → **code**.
- Rapport, friction handling, phrasing, disclosure delivery → **LLM**.
- Why it matters: the agent literally *cannot* speak a number it wasn't served → no bluffing.

### 6 · Disclosure & honesty (MANDATED)
- Discloses AI + acting-for-patient in the first ~30s; **never denies it** when asked ("Am I
  talking to a robot?" → "You are…"). The Luo 2019 disclosure penalty is real; we beat it with
  competence, not concealment.
- **Honesty audit** on every call: figures diffed vs. the DB, case-facts vs. the JobSpec →
  "passed" badge in the report. Never invents inventory, a fake bid, or hardship.
- *Visual: the disclosure line + a redacted honesty-audit badge.*

### 7 · The demo — a real price move
The showstopper arc, as a ticker: **$4,287 → $3,875 → $2,400 → $1,650. −62%.**
Each step tied to a lever the agent gathered (duplicate cite → benchmark cite → settlement).
3 distinct counterparty styles (Stonewaller hangs up → documented decline; Policy-Citer →
charity app; Collections → settlement). *Embed the 3:30 video / QR.*

### 8 · Config-swap vision + team (MANDATED)
- Vertical params are **config, not code**: swap `medical_bills.yaml` → `moving.yaml`, same
  engine negotiates moving quotes. *Visual: the two config files side by side.*
- Beachhead → generalizes to contractors, auto repair, freight — any market priced by phone.
- Team + `hagglfor.me`. Ask / what's next.

---

## Submission text (draft)

**Tagline:** Haggle — an AI advocate that calls your hospital's billing office and negotiates
your bill down, live.

**Short description (≈100 words):**
> Medical bills are opaque, error-ridden, and negotiable — but almost nobody makes the calls.
> Haggle does. Upload your hospital bill and EOB; a voice agent parses them, runs a short
> interview, and finds the billing errors and the legal levers on your side (No Surprises Act,
> §501(r) charity care, and the hospital's own published prices). Then it places real phone
> calls and negotiates — disclosing it's an AI, never bluffing, and citing only numbers our
> deterministic engine computed. In our demo it takes a $4,287 ER balance to $1,650 — 62% off —
> on a live call, every step caused by gathered leverage. Swap one config file and the same
> engine negotiates moving quotes.

**What it demonstrates (judge checklist):** closed loop (intake→calls→negotiation→ranked
report); one JobSpec from voice + document, reused verbatim; live calls vs. 3+ distinct
negotiation styles; a mid-call price move caused by leverage, not script; AI disclosure +
honesty audit; every call ends in a structured outcome; ranked report with transcript
citations. Built on ElevenLabs Agents + Twilio, FastAPI, Supabase, Next.js.

**Honest about the hard parts:** counterparties are our own reactive counter-agents + a live
human role-player (a brief-sanctioned setup); the benchmark methodology runs on real hospital
price-transparency files (the demo hospital "Mercy General" is fictional, its figures labeled as
demo data); Medicare rates and legal artifacts (HIPAA authorization) are flagged where mocked.
