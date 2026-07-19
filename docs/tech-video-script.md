# Tech Video · 60-Second Script (stack, architecture, implementation) · Owner: Kar Shin

Submission slot: **Tech Video (max 60 sec)**, "Technical explanation: cover your stack,
architecture, and implementation."

Visual: screen-record **`/tech-video`** on hagglfor.me (or `npm run dev` then
`http://localhost:3000/tech-video`). The page is a 6-slide deck timed to this script.
Press **Space** to start the 60-second auto-run (slides advance on the beat marks, every
element animates in), or use ←/→ to drive it manually. 1280×800 stage, same recording
setup as the pitch deck.

Read this out loud once before you record. If a line doesn't sound like something you'd
actually say to a friend, change it. That's the bar, not word count.

---

### 0:00 to 0:08 · Slide 1 · "we kept the stack boring"
**[SCREEN]** Five-box service strip: Next.js, FastAPI, Supabase, ElevenLabs, Twilio.
**[V]** "Here's the stack, and it's boring on purpose. Next.js, FastAPI, Supabase.
ElevenLabs agents dial out through Twilio, so every call is a real phone call."

### 0:08 to 0:22 · Slide 2 · "the AI never picks the price"
**[SCREEN]** Mid-call loop: rep stonewalls, `report_lever_result`, `advance()` forces `reach_authority`; the 9-rung ladder.
**[V]** "The AI never picks the price. That's the one rule we wouldn't bend. There's a
state machine underneath it, walking a ladder we wrote in config. The voice agent talks,
but the server decides what happens next. Try to offer more than the patient can pay,
and it just won't let you say it."

### 0:22 to 0:35 · Slide 3 · "we made sure it never bluffs"
**[SCREEN]** THE SCARE (invented CPT code), THE FIX (four webhook tools), THE PROOF (real MGH price file, $2,633.25).
**[V]** "Honest story: on our very first test call, it made up a billing code. So we
locked it down. Now it can only say things that come through a tool, and those numbers
come from Mass General's real published price file. It doesn't get to invent anything,
and it never denies being an AI if you ask."

### 0:35 to 0:45 · Slide 4 · "there is no demo mode"
**[SCREEN]** Negotiator → PSTN → personas / human cell; `call_events` → Realtime → War Room.
**[V]** "There's no demo mode here. Persona calls and the real human call go through the
exact same phone line and land in the War Room the exact same way. When we switched to
live calls, nothing in the UI had to change."

### 0:45 to 0:55 · Slide 5 · "new market? one file"
**[SCREEN]** `medical_bills.yaml` next to `moving.yaml`.
**[V]** "Want a different market? That's one config file, not a rewrite. Swap medical
bills for moving quotes, and the same engine just runs."

### 0:55 to 1:00 · Slide 6 · Close (dark card)
**[SCREEN]** "Code decides what's true. The model decides how to say it." Wordmark, hagglfor.me.
**[V]** "Code decides what's true. The model just decides how to say it. That's Haggl."

---

## Why this covers the brief

| What the judges are told to look for | Where it lands |
|---|---|
| Stack | 0:00 to 0:08, all five services named |
| Architecture | 0:08 to 0:22 and 0:45 to 0:55 |
| Implementation | 0:22 to 0:45 |
| Real negotiation, price moves for a reason | Slide 2, the state machine is the mechanism, not a script |
| Honest about the hard parts | Slide 3, a real failure and the fix, not a highlight reel |
| Where the honesty line sits | Slide 3, tool-gated numbers, never denies being an AI |
| Config, not code | Slide 5, the brief's own phrase, then the two real YAML files |
| Several negotiation styles, one real path | Slide 4, personas and a human on the same transport |

## Production notes
- Record at 1280×800. The stage scales itself, same as the pitch deck.
- Space plays the full 60 seconds. R resets to the start.
- Read it like you're explaining it to someone at the table next to you, not presenting
  to a room. Slower than you think, with real pauses.
- If a take runs long, the first thing to cut is the last sentence of slide 2 or slide 4,
  they're the least load-bearing.
