# Submission Videos — Production Notes

> **The shipped submission cut is v3.** See the **"v3 (FINAL, submission cut)"** section at the bottom of this file for the final offsets, segment table, hero-call provenance, and one-command re-run steps. The v1 and v2 notes below are kept for history.

Two 60-second submission videos, v1. Built from live captures of `127.0.0.1:3000`
(the stable local build) + ElevenLabs VO (voice **Jason**, `eleven_flash_v2`).
Assembled with the bundled ffmpeg (`imageio_ffmpeg`), H.264/AAC, 1280×800, 25fps.

| File | What it is | Duration | Audio | Status |
|---|---|---|---|---|
| `tech-video-v1.mp4` | **Deliverable A** — tech video, finished v1 | 60.00s | yes (6 VO beats) | ✅ ship-ready |
| `uiux-video-v1.mp4` | **Deliverable B** — UI/UX video, best-effort v1 | 60.00s | yes (5 VO lines) | 🟡 v1 for team; Shot 5 is a labelled placeholder |
| `a-shot1-landing.webm` | raw clip — landing hero | 6.8s | no | ✅ |
| `a-shot2-intake.webm` | raw clip — intake upload + parse + voice card | 20.1s | no | ✅ |
| `a-shot3-diagnosis.webm` | raw clip — bill Diagnosis findings scroll | 10.1s | no | ✅ |
| `a-shot4-approve-warroom.webm` | raw clip — approve → War Room grid → single call | 17.0s | no | ✅ |
| `a-shot5-warroom-replay.webm` | raw clip — single-call view, live ticker (FALLBACK) | 36.0s | no | 🟡 see Shot 5 |
| `a-shot6-report.webm` | raw clip — report + audio player + paper trail | 10.7s | no | ✅ |

The **raw webm clips are the real Deliverable-B kit** — longer than the script's slots on
purpose, so the editor has room. The `uiux-video-v1.mp4` is a rough cut to react to.

---

## Deliverable A — tech-video-v1.mp4 (finished)

- Recorded `/tech-video` (the 6-slide auto-run deck), pressed Space, captured the full 60s
  auto-run. Trimmed the 2.4s pre-play lead-in so play-relative t=0 == video t=0.
- VO: the script's 6 beats, one mp3 each, placed at their beat offsets (0 / 8 / 22 / 35 / 45 / 55s)
  via ffmpeg `adelay`+`amix`.
- **VO text: unchanged from the script.** Three beats were re-read at **speed 1.15** (b0 "boring
  stack", b2 "never bluffs", b3 "no demo mode") because at speed 1.0 they overran their beat
  slots and collided with the next line. b1/b4/b5 are speed 1.0. No wording was altered.
- QA (frames viewed): 10s → Slide 2 "the AI never picks the price" (clock 10.0s); 30s → Slide 3
  "we made sure it never bluffs" ($2,633.25 proof, clock 30.1s); 55s → Slide 6 close card
  "Code decides what's true" (clock 55.1s). **Slides advance correctly and VO tracks the beats.**

## Deliverable B — uiux-video-v1.mp4 (best-effort v1)

Cut = Shot1 (hero) → Shot2 (parse result + findings) → Shot3 (diagnosis) → Shot4 (approve →
War Room grid) → **Shot5 placeholder** → Shot6 (report). VO at ~0 / 5 / 15 / 22 / (silent) / 50s.
Shot 5 is the `a-shot5` footage with a **burned-in caption**: *"live call block — recording with
Jay pending"* (bottom-center, per the brief). VO is silent over the call block, as the script requires.
VO text is **verbatim from the script** (voice Jason), speed 1.0.

QA (frames viewed): hero ✅, parse result "23 line items extracted / Matches your case records" ✅,
War Room grid of ● LIVE cards ✅, Shot-5 caption renders ✅, report "$980 → $392 (−$588) Resolved,
ref MRS-55217" ✅.

---

## ⚠️ Shot 5 — what still needs the human call

The script's centerpiece is a **~32s continuous live call** with **Jay role-playing "Pat"**
(`prompts/personas/human_role_play_guide.md`). That cannot be produced without Jay on the phone,
so `a-shot5-warroom-replay.webm` is the **honest fallback** the script's Shot-5 fallback clause
describes: the real single-call War Room view (`/warroom?call_id=…`), UI-identical code path,
with the ticker and milestone feed moving live.

**Important divergence:** the fallback shows the **collections** counterparty (Meridian Recovery
Services, **$980 → $392, −60%**), **not** the hero hospital arc ($4,287 → $1,650, −62%). Reason:
a default `POST /calls/launch {simulate:true}` maps the `facility` entity to the
`gruff_stonewaller` persona (it stonewalls and hangs up — the ticker stays at $4,287). The
$4,287→$1,650 arc lives in the `human_facility_supervisor` persona, which is **not wired to any
entity in the live config** (`config/verticals/medical_bills.yaml` → `simulator.entity_personas.facility: gruff_stonewaller`).
Meridian's collections arc was the best *moving* single-call ticker available from a default launch.

Two ways to get the real centerpiece:
1. **The real call (preferred):** Jay as Pat over PSTN via `apps/api/app/routers/calls.py::place_real_call`
   (`POST /calls/place-real`) or `place_test_call.py`, recorded through the same
   `/warroom?call_id=<id>` single-call view.
2. **Simulated hero arc (fast placeholder upgrade):** set
   `simulator.entity_personas.facility: human_facility_supervisor` in
   `config/verticals/medical_bills.yaml`, **restart the API** (ENTITY_PERSONAS is read at import),
   `POST /calls/launch {"case_id":"demo","simulate":true}`, then record the *Mercy General
   Hospital* call's single view — you'll get $4,287 → $3,875 → $2,400 → $1,650 with the levers
   arming before each move. (Not done here: the brief says do not restart the running server.)

---

## 📋 Script-vs-current-UI divergences (for Kar Shin — please update the scripts)

Both scripts describe an older build. What the live app actually does now:

1. **Voice is Jason, not Adam.** Video A script says "Voice = Adam"; the deployed/agreed voice is
   **Jason** (`8duqbsrxNeN6j4yugadv`). All VO in both videos is Jason. The `/voice` picker copy in
   the script ("Adam · Assertive and unbudging") will not match.
2. **Approve/launch lives on `/confirm`, not the bill's Plan tab.** Video A Shot 3–4 expect
   "bill → Plan tab → Start the calls". The actual control is on **`/confirm`**:
   **"Looks right, make the calls"** — clicking it **auto-launches the simulated calls AND routes
   straight to `/warroom`** (grid). There is no separate "Start the calls" step on the Plan tab.
3. **The bill-detail tabs all work now.** Script's live note said "the Plan tab didn't switch
   content." Verified: **Diagnosis / Plan / Call History / Action Items (2) / Documents** all switch
   content (Plan shows the negotiation ladder / "rung" / launch copy).
4. **War Room single-call view has COVERAGE + DOCUMENTS panels, not an "Advocates" panel.** Script
   Shot 4 says "Advocates panel on the right." Reality: the right rail is a **Coverage** panel
   (required-questions progress) + a **Documents** rail (Bill / EOB tabs). Coverage+Documents render
   **only in the single-call view** (`?call_id=`); the **grid overview** shows the LIVE call cards +
   a Documents rail but no Coverage panel.
5. **Intake voice interview is LIVE, not "offline".** Script's live note said `/intake` shows
   "Voice interview is offline." Reality on this build: the embedded **ElevenLabs convai widget is
   present** (floating "Need help? / Start a call" + the "confirm what we heard? Enter your numbers"
   link), i.e. `NEXT_PUBLIC_ELEVENLABS_AGENT_ID_INTAKE` is set. The voice-interview card reads
   "A two-minute conversation."
6. **The "See the report →" CTA is deployed.** Script's live note flagged it as PR #56 "not yet
   deployed." It's present now — as a banner in the War Room grid ("Some calls have wrapped up.
   See every outcome… See the report →").
7. **Upload is a two-step gesture.** Selecting a file opens a **preview modal**; you must click
   **"Attach this document"** to start the parse. (Good for the demo — the real PDF pops up first.)
8. **Bill/EOB iframe renders blank in headless capture.** In the War Room Documents panel and the
   `/intake` preview, the embedded PDF iframe shows a **blank white frame** under headless Chromium
   (its PDF viewer is disabled). It should render in a real/headed browser — re-record headed, or
   swap the iframe for a rendered page image for the edit.
9. **Numbers reconcile.** Bill $4,287 (EOB $3,875), 4 findings totalling $3,065 flagged
   (dup 71046 +$412 · upcode 99285 +$2,011 · unbundle 80053 +$642 · EOB mismatch +$412), report
   settles Meridian $980→$392. All matches `data/seed/demo_answer_key.json`.

---

## Exact re-record instructions

**Setup (once):** venv `apps/api/.venv`; `pip install playwright imageio-ffmpeg && playwright install chromium`.
ffmpeg path: `python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`.
Login for logged-in shots: **maya@hagglfor.me / HagglDemo2026!** (save `storage_state`, reuse).
All recording = Playwright chromium, context viewport 1280×800 + `record_video` 1280×800 → webm.

The exact scripts used are archived in `/Users/hamza/.claude/jobs/bb773a14/tmp/`:
`rec_tech.py`, `rec_shots.py` (shots 1/2/3/4/6, arg = shot number), `rec_shot5.py`,
`login.py`, `tts.py` (+ `tech_vo.json`, `uiux_vo.json`), `assemble_uiux.py`.

Per shot:
- **Shot 1** — goto `/` (logged out for the clean marketing hero), hold ~4s.
- **Shot 2** — logged in, `/intake`; `set_input_files` on the first `input[type=file]` with
  `data/demo_docs/mercy_general_bill.pdf`; **click "Attach this document"**; wait for
  "…extracted"; hold; smooth-scroll to the voice-interview card.
- **Shot 3** — logged in, `/bills/00000000-0000-0000-0000-000000000001`; slow-scroll the Diagnosis findings.
- **Shot 4** — logged in, `/confirm` (use `wait_until="domcontentloaded"` — the page holds a live
  socket and never hits networkidle); click **"Looks right, make the calls"**; it launches sims +
  routes to `/warroom`; hold on the grid; optionally click a `a.wr-call-card` to reveal
  Coverage+Documents in the single view.
- **Shot 5 (fallback)** — `POST http://127.0.0.1:8000/calls/launch {"case_id":"demo","simulate":true}`;
  pick the launched call whose `entity == "Meridian Recovery Services"` (best moving ticker) OR the
  hospital call if the config flip above is applied; open `/warroom?call_id=<id>` immediately and
  record ~35s. First ~8s is the "connected, waiting" state; the ticker starts moving ~10s in.
- **Shot 6** — logged in, `/report` (`domcontentloaded`); wait for "Recorded authorization on file";
  hold ~3s on the header + audio player; scroll to the resolved section; click `.paper-trail-toggle`
  to expand a paper trail.

**Assembly:** trim each clip to its slot, `concat`, burn the Shot-5 caption with `drawtext`
(font `/System/Library/Fonts/Supplemental/Arial.ttf`), overlay VO with `adelay`+`amix`
(`normalize=0`), encode `libx264 -crf 20 -pix_fmt yuv420p` + `aac`, `-t 60`. See `assemble_uiux.py`.

---

## v3 (FINAL, submission cut): supersedes v1 and v2

v2 was rejected for wrong voices, crammed pacing, and a stitched call block. v3 fixes all three: **Jason narrates the entire tech video**, **Sarah narrates the entire demo video**, pacing returns to v1-style long holds, and the call block is **one continuous real exchange** with no fragments.

| File | What | Duration | Audio | Loudness |
|---|---|---|---|---|
| `tech-video-v3.mp4` | Deliverable 1, tech | 60.00s | Jason VO x6 | -16.1 LUFS int, TP -1.5 dBFS |
| `uiux-video-v3.mp4` | Deliverable 2, demo | 60.00s | Sarah VO x5 plus real call | -16.5 LUFS int, TP -1.5 dBFS |

Both are 1280x800, H.264 plus AAC, 25fps, built with the bundled `imageio_ffmpeg` ffmpeg.

**Voices (final):**
- Tech: **Jason** `8duqbsrxNeN6j4yugadv`, all 6 beats, no other narrator.
- Demo: **Sarah** `EXAVITQu4vr4xnSDxMaL`, all 5 lines. The call block has no VO; the real call audio carries it.

### Deliverable 1: tech-video-v3.mp4

Recorded the live `/tech-video` deck fresh (it changed the night before: slide 1 now has six service cards including OpenAI, slides 2 and 4 carry the architecture-page diagrams). The deck is 6 slides auto-advancing at beats 0 / 9 / 22 / 35 / 45 / 55s; the on-screen `#clock` counts from the Space press.

**Lead-in measurement:** frames at raw 5 / 32 / 52s showed the clock reading 03.8 / 30.8 / 50.8s, so the Space press sits 1.20s into the recording. Trim raw `[1.20, 61.20]` so Space equals t0.

**VO offsets** (measured durations in parentheses), placed by `adelay` plus `amix`:
`b0@0.3 (7.97)`, `b1@9.0 (11.23)`, `b2@22.0 (8.67)`, `b3@34.5 (11.47)`, `b4@46.1 (8.99)`, `b5@55.3 (3.32)`. No overlap; the tightest gap is b3 to b4 at 0.13s. loudnorm `I=-16 TP=-1.5`, 120ms tail fades, alimiter 0.89.

**QA:** deck frames 5=S0 (six cards including OpenAI), 15=S1 (one negotiation turn), 30=S2 (the code holds the line), 40=S3 (runtime topology diagram), 50=S4 (new market, one file, 9 scenarios), 58=S5 (closer). Exactly 60.00s, integrated -16.1 LUFS, true peak -1.5 dBFS, no overflow on any beat.

### Deliverable 2: uiux-video-v3.mp4 (v1 pacing)

Segment table (global seconds):

| Seg | Content | Source | Trim | Global |
|---|---|---|---|---|
| A | cold open, 3-beat stat card | `a-segA-coldopen-v3.webm` | 0.10 to 9.10 | 0.0 to 9.0 |
| B | landing hero | `a-shot1-landing.webm` | 1.0 to 6.0 | 9.0 to 14.0 |
| C | intake upload and parse | `a-shot2-intake.webm` | 12.5 to 22.0 | 14.0 to 23.5 |
| D | diagnosis findings, slow scroll | `a-shot3-diagnosis.webm` | 3.2 to 11.2 | 23.5 to 31.5 |
| E | confirm, then War Room goes live | `a-shot4-approve-warroom.webm` | 6.0 to 10.5 | 31.5 to 36.0 |
| F | the call (one continuous exchange) | `segF_call_v3.mp4` | 0.0 to 13.5 | 36.0 to 49.5 |
| G | case file report | `a-shot6-report.webm` | 3.74 to 12.04 | 49.5 to 57.8 |
| H | end card | `endcard.png` | 0.0 to 2.2 | 57.8 to 60.0 |

Total 60.00s.

**Sarah VO offsets** (measured durations), collision-checked against each other and against the call audio:
`vo1@0.40 (15.73)` spans A into B on purpose. `vo2@16.18 (7.47)` over C. `vo3@23.70 (7.89)` over D. `vo4@31.64 (4.36)` over E, ends 36.00 which clears the call start at 36.10. `vo6@49.45 (10.53)` over G, starts after the call ends at 49.40 and ends at 59.98.

Deviation from the brief's suggested offsets: `vo2@14.4` would have overlapped `vo1` (which ends at 16.13 at the measured 15.73s length), so vo2 was nudged to 16.18. vo3 and vo4 landed within 0.3s of the brief. This is the "adjust" the brief anticipated.

**Cold open (rebuilt):** `coldopen_build_v3.py` renders three beats over about eight seconds in the dark Haggl aesthetic with embedded Bricolage Grotesque and General Sans fonts: "Up to 4 in 5 hospital bills contain errors", then "93% who negotiate get a reduction, 64% never even ask", then "Maya, our demo patient: a $4,287 ER bill". Recorded 10s headless, trimmed to 9s.

**Seg F, the call, one continuous window, no stitching:**
- Audio: `hero-call.mp3` trimmed `[76.65, 89.95]` (13.30s). This is Morgan's single turn (transcript turn at 77s: "Let me pull that up. Yeah, okay. I've got two of the seven one and four six on the same date. I'll put an adjustment in for the one. That brings you to three thousand eight hundred seventy-five."), bounded by the next agent turn at 91s. silencedetect confirms a 3.39s pause ending 76.89s (Morgan's first word) and a 6.3s pause starting 89.69s (last word), so both cut points fall inside silence. 150ms fades at the edges only; nothing is clipped mid-word.
- Video: `hero2-warroom.webm` trimmed `[79.15, 92.65]` (13.5s). The live balance shows "negotiating", then reveals **$3,875** at about webm 88.7s with the milestone "quote to $3,875", aligned to Morgan speaking the figure (about seg-local 9.55s, global 45.55s). $3,875 stays stable through 117s. There is no large $4,287 numeral in this recording; the reduction reads as the reveal, and $4,287 is established by the cold open, the diagnosis, the report, and the end card.
- Caption bottom-left: "real call, two AI agents, unscripted". Call audio loudnorm `I=-16`, never ducked (it is the only audio in Seg F).

**QA:** every segment boundary frame verified on the correct beat; the $3,875 reveal is visible in F at about 45.5s with the caption; the cold open text is legible; the call audio plays continuously with only the transcript's natural intra-turn pauses (no mid-word cut); total 60.00s, integrated -16.5 LUFS, true peak -1.5 dBFS.

### Hero-call provenance

`conv_8701kxwv7yj8e8zvs9w7s8s0k3qv` is a **212s real PSTN agent-to-agent call**: our negotiator agent "Alex" against the **persona-supervisor agent "Morgan"** (a billing supervisor persona), placed over a real phone line. This is the genuine continuous exchange that the v1 notes' Shot 5 gap was waiting on: no human role-play, no `simulate` flag, no stitching. Full audio is `hero-call.mp3` (212s). Pull the transcript with per-turn `time_in_call_secs` via:
`GET https://api.elevenlabs.io/v1/convai/conversations/conv_8701kxwv7yj8e8zvs9w7s8s0k3qv` with header `xi-api-key: <ELEVENLABS_API_KEY from root .env>`.
The full arc is $4,287 to $3,875 (duplicate 71046 removed) to $2,400 to $1,650 paid in full, reference MG-ADJ-2247. v3 uses the $4,287 to $3,875 duplicate-removal exchange because it is the single cleanest continuous concession.

### One-command re-run per artifact

`PY = apps/api/.venv/bin/python`; ffmpeg path is `$(PY -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")`. All scripts are archived in `/Users/hamza/.claude/jobs/bb773a14/tmp/`. The web server on `127.0.0.1:3000` must be up; recording is read-only.

1. Tech deck capture: `cd apps/web && $PY tech_rec_v3.py` produces `tech-live-v3.webm` (drives `127.0.0.1:3000/tech-video`, presses Space, records about 64s).
2. Tech assemble: `$PY tech_assemble_v3.py` produces `deck/video/tech-video-v3.mp4`.
3. Cold open: `$PY coldopen_build_v3.py && $PY coldopen_rec_v3.py` produces `a-segA-coldopen-v3.webm`.
4. Seg F call: `$PY segf_build_v3.py` produces `segF_call_v3.mp4` from `hero2-warroom.webm` and `hero-call.mp3`.
5. Demo assemble: `$PY master_uiux_v3.py` produces `deck/video/uiux-video-v3.mp4`.

The UI shots `a-shot1` through `a-shot6` are the fresh post-cleanup captures in `video-raw` (note: `a-shot5-warroom-replay.webm` is the OLD clip and is not used in v3).
