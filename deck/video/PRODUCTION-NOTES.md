# Submission Videos — v1 Production Notes

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
