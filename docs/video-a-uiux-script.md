# VIDEO A — UI/UX Showcase · 60s Shooting Script

> Director/VO: **Kar Shin** · Phone rep: **Jay as "Pat"** (live human role-play, `prompts/personas/human_role_play_guide.md`)
> Record on the **live site https://hagglfor.me** (address bar visible — it's real).
> Focus: user experience + product flow, with a **~30s continuous live call** at the center.
> Numbers reconcile with `data/seed/demo_answer_key.json`. Supersedes Video A in `docs/demo-shot-lists.md` (keeps its S-criteria coverage; restructured for one continuous call instead of fast cuts).

## The one-line story
Upload a confusing hospital bill → Haggl finds the errors → you approve → an AI voice negotiates it down **live on a real call** → ranked, cited report. −62%.

## VO word budget
Total spoken VO ≈ **82 words** (~150 wpm). VO is SILENT during the call block — the call audio is the star. Record VO after the screen capture, to picture.

---

## Navigation & transitions — budget ~5s for the clicks
You don't teleport between screens; each cut lands on a click, and page loads take a beat. The app has a **persistent top nav** (Bills · Action Items · Voice · Profile · War Room · Case file) and the bill detail has **tabs** (Diagnosis · Plan · Call History · Documents). Budget these so the flow reads, not jumps:

| # | The click | Lands on | Budget |
|---|---|---|---|
| 1 | Landing hero → `Start saving, it's free →` (or Log in) | the app (Bills) | ~1s |
| 2 | Upload on `/intake`; parse runs → opens the bill | Bill detail (Diagnosis) | ~1s load |
| 3 | On `/confirm`: `Looks right, make the calls` | launches the calls AND routes to the War Room | ~1.5s |
| 4 | Land in the War Room; click a call card for the single-call view | War Room | ~0.5s |
| 5 | Call ends → the `See the report →` CTA in the War Room grid | Report (Case file) | ~1s |

---

## SHOT LIST

### SHOT 1 · 0:00–0:03 · The brand (3s)
**SCREEN:** `hagglfor.me` landing hero — "your medical bill just met its match," floating bill motif, URL in the address bar.
**Screenshot ref:** `deck/assets/home-hero.png` (frame it exactly like this).
**VO:** *"Maya owes $4,287 for one ER visit — with insurance."*
**On-screen text:** none (the hero speaks).

> ▸ *transition 0:03–0:04 (~1s): click `Start saving` → app opens on the bill (signed in as maya@hagglfor.me).*

### SHOT 2 · 0:04–0:11 · Intake: document + voice (7s) — proves S2
**SCREEN:** `/intake` (logged in as `maya@hagglfor.me`): drag `data/demo_docs/mercy_general_bill.pdf` into the upload card → parse animation ("line items extracted") → **quick cut** to the embedded ElevenLabs voice-interview widget mid-question.
**Screenshot ref:** capture live at `hagglfor.me/intake` (no repo PNG yet — REHEARSAL NOTE: the vision parse takes ~10s real time; start the upload before the in-point and film the tail of it).
**AUDIO (real widget, 3s):** Intake: *"…what could you comfortably pay today?"* → Maya: *"Maybe seventeen hundred."*
**VO (over the upload, before the audio):** *"Upload the bill. A short voice interview asks only what documents can't answer."*

> ▸ *transition 0:11–0:12 (~1s): parse finishes → the bill opens on the Diagnosis view. Let the load beat land.*

### SHOT 3 · 0:12–0:18 · Diagnosis: the findings (6s) — proves S2 (spec) + sets up S4
**SCREEN:** Bill detail → **Diagnosis** tab (`/bills/…0001`): "THE CENTRAL ARGUMENT" card, then the **4 findings** with dollar chips — Duplicate 71046 **+$412** · Upcode 99285 **+$2,011** · Unbundle 80053 **+$642** · EOB mismatch **+$412** · "TOTAL FLAGGED: $3,065". Slow scroll down the findings; end on the projected-savings bar ($1,327–$2,653 possible).
**Screenshot ref:** live capture of the Diagnosis tab (layout as toured 07-18: title row $3,875/$4,287, savings bar, findings cards).
**VO:** *"Haggl reads it like an auditor: four billing errors, three thousand dollars flagged — each one with evidence."*

### SHOT 4 · 0:18–0:20 · Approve → War Room fills (2s = the transition) — proves S2 gate, S3 setup
This shot IS the navigation into the call: on `/confirm`, `Looks right, make the calls` → hard cut to the dark War Room going ● LIVE. The contrast (light bill → dark War Room) is the drama; don't linger.
**SCREEN:** The approve moment (`/confirm` → `Looks right, make the calls`, which auto-launches the sims and routes straight to the War Room), **1s beat** on the Voice picker strip if it fits (`/voice` — "On calls we'll use — Jason · Calm and unhurried"), then the **War Room** (`/warroom`): dark theme, call cards going ● LIVE. Click a card for the single-call view, where the right rail is a **Coverage** panel (required questions flip red→green live) over a **Documents** rail (Bill / EOB).
**Screenshot refs:** `deck/assets/warroom.png` + live `/voice` capture. CUT-IF-OVER: the voice-picker beat is the first thing to drop if the edit runs long.
**VO:** *"Maya approves — nothing dials until she does. Then Haggl picks up the phone."*

### SHOT 5 · 0:20–0:52 · THE LIVE CALL (32s, continuous) — proves S4, S5, S6
**SCREEN:** War Room call view, full frame. The through-line is the **price ticker** — it must be readable the whole time: **$4,287 → $3,875 → $2,400 → $1,650**, lever chips arming before each move, `escalation_required` event firing at $1,650. Picture-in-picture (small): Jay on a real phone, or the phone screen with the inbound call — sells "live human on the line."
**AUDIO:** the call IS the audio. No VO. Record the full call with Jay as Pat (concession rules in `human_role_play_guide.md`); cut to these beats, ticker carrying continuity:

**Realism rule: no instant concessions.** Pat never gives ground on the first breath — every move gets a *consideration beat* first (a system check, a deflection, a grumble). That friction is what makes the movement read as earned, not scripted (the judges' explicit red flag).

| ~t | Beat (agent = Jason's voice) | Ticker |
|---|---|---|
| 0:20 | Alex, easing in: *"Hi, this is Alex. Have I reached the billing office at Mercy General, and who am I speaking with?"* Pat, wary: *"…what is it you're asking for?"* | $4,287 |
| 0:25 | The duplicate, plain: *"So the chest X-ray, June second — code 7-1-0-4-6 — it's on here twice. Can you take one off?"* | $4,287 |
| 0:29 | **Consideration beat.** Pat: *"Hold on… let me pull that up."* — keys clacking, a pause — *"…we bill what's documented, sir."* Alex, easy: *"Sure — but it's the same code, same day. Two X-rays, one visit."* Pat, beat: *"…hm. Yeah, okay, I do see it twice. I can put in an adjustment for one."* | **→ $3,875** |
| 0:37 | The benchmark, slow and clean: *"Appreciate that. Now — Medicare pays four thirty-eight for these codes… and your own posted cash price is twenty-six thirty-three."* Pat, bristling: *"Our rates are our rates."* — pause — *"…look, I've got some room. Best I can do is 2,400."* | **→ $2,400** |
| 0:46 | The close: *"She can do sixteen-fifty today, paid in full — can you take that to your supervisor?"* Pat, exhaling: *"…give me a second."* — hold music, 2s — *"Okay. Approved at 1,650."* | **→ $1,650** |
| 0:51 | Wrap: *"Appreciate you, Pat."* Reference `MG-ADJ-2247` lands as an outcome card; `escalation_required` chip = a human signs off the final number. | settled |

*(Timing note: call block 0:20–0:52 leaves ~5s of the 60 for navigation clicks and 0:53–0:58 for the report + a 2s end card. The ~4s earlier start vs. the pre-nav version is exactly the transition budget moved up front.)*

**On-screen text (small, bottom):** at 0:29 "finding #1: duplicate charge" · at 0:37 "the hospital's own posted price" · at 0:52 "every call ends structured: ref MG-ADJ-2247".
**FALLBACK:** if the live take breaks twice, use the best golden recording replayed through the identical War Room view (the UI is the same code path) — label honestly in the submission text, not on screen.

> ▸ *transition 0:52–0:53 (~1s): call ends → click the `See the report →` CTA (now live in the War Room grid). Before that banner there was no clear way out of the War Room.*

### SHOT 6 · 0:53–0:58 · The receipt (5s) — proves S7 + closes S1
**SCREEN:** `/report` (or bill → Call History/outcome view): ranked outcomes with ref#s + rep names, **billed vs fair vs achieved** per line, Evidence expanded to a cited transcript line, then the savings headline.
**Screenshot ref:** `deck/assets/report.png`.
**VO:** *"Ranked, cited, in plain English. $4,287 became $1,650 — sixty-two percent off. Haggl."*
**End card (1s):** Haggl logo + `hagglfor.me`.

---

## Success-criteria map (Challenge.pdf) — what this 60s proves on camera

| Criterion | Where |
|---|---|
| S1 loop closed (intake → calls → negotiation → recommendation) | Shots 2→6, whole arc |
| S2 one spec: voice interview + document, user-confirmed, reused | Shots 2 (both paths), 4 (the gate) |
| S3 ≥3 styles / structured quotes | Shot 4 (parallel cards) — fully covered in Video B; here we show the *fleet*, prove one deeply |
| S4 price moves mid-call from leverage | Shot 5 — the entire block, ticker on screen |
| S5 disclosure + honesty | Shot 5 (if Pat asks "robot?", Alex confirms honestly — Jay may inject it per the guide); honesty audit shown in Video B |
| S6 structured outcomes | Shot 5 close (ref MG-ADJ-2247 outcome card) + Shot 6 |
| S7 ranked, cited report | Shot 6 |

## Pre-shoot checklist
- [ ] Jay rehearsed the role-play guide twice (concessions ONLY on the cited cues; floor $1,500)
- [ ] Demo reset run (Maya's case fresh; War Room clean); logged in as `maya@hagglfor.me`
- [ ] Screen capture at 1080p+, address bar visible; phone PiP framed if using it
- [ ] Voice = Jason (Voice tab shows "In use ✓"); intake widget mic-checked
- [ ] Full call recorded once uncut (it's also golden-call + eval material), then edit to the beat map
- [ ] VO recorded to picture, −14 LUFS-ish, call audio ducked never muted
