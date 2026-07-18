Generate a high-fidelity static UI mock for the "War Room" screen of Haggl — a product that reads a user's medical bill, finds errors and legal leverage, calls the billing office as an AI voice agent, and negotiates the balance down. This is a demo/judge-facing screen for a hackathon presentation (not part of the everyday consumer product) — its entire purpose is to prove, visually, that the negotiation is driven by real backend logic and a real live phone call, not a scripted demo.

## Design system — follow exactly

**Brand personality:** warm, a little irreverent, financially-themed (cash motifs, not medical iconography). The rest of the product (Onboarding, Bill List, Bill Detail, Action Items) is calm and restrained — but War Room is the one screen allowed more visual energy and intensity, since it needs to read clearly from across a room during a live presentation.

**Color:**
- Background: `#FAF7F2` warm off-white (or you may go slightly darker/higher-contrast for this screen specifically, since it needs stage presence — a deep warm charcoal background is worth considering here as the one departure from the product's light palette, IF it makes the price ticker and live indicators pop harder. Use your judgment, but stay in the same warm (not cool/blue) family.)
- Surface/card: `#FFFFFF` (or dark-surface equivalent if you go the dark-background route) with `#F5F1EC` muted variant
- Text primary: `#1A1410` (warm black, never pure black) — or off-white equivalent on dark
- Text secondary: `#6B6058`
- Accent (coral): `#EF6B45`, hover `#D95A34`, tint `#FCE3D8` — the ONLY "win"/positive color. Used for the price ticker, savings figures, positive/settled states. Never use green.
- Flag/attention (amber): `#C98A2E`, tint `#F6E7CC` — used for in-progress/pending states, not errors specifically on this screen
- Destructive (red): `#C4483A` — reserved only for true failure/decline states
- Border: `#E8DDD3` (or a low-opacity warm border on dark)

**Typography:**
- Display/headline font: Bricolage Grotesque (bold, rounded, chunky grotesque) — used for the price ticker specifically, this should be the largest, boldest text on the entire screen
- Body/UI font: General Sans
- Monospace font: IBM Plex Mono — used for ALL technical/factual content: tool-call logs, dollar amounts, CPT codes, timestamps, reference numbers. This is critical to this screen's purpose — mono type is what signals "this is a real system event, not narrative."

**Shape and depth:** full pill radius on buttons/badges/status chips, 16px radius on cards, one subtle shadow tier for card hierarchy, no heavier shadows.

## The screen

Focus on **ONE live call** — not multiple parallel calls (there's no need to show three simultaneous call cards; this screen goes deep on a single call instead of wide across several). Layout: two side-by-side panels, roughly equal width, on a single screen.

**Demo content to use** (for realism): Maya's case, calling Mercy General Hospital's billing supervisor about her ER visit balance. Balance moving from $4,287 to $3,875 (duplicate chest X-ray charge conceded) to a final settlement of $1,650. Benchmark citations: Medicare rate $438, Mercy's own posted cash price $1,890. Lever being armed: duplicate-charge dispute (CPT 71046), followed by price-benchmark citation, followed by lump-sum settlement offer.

### Left panel — the human side
What this call sounds and reads like:
- An audio player/waveform visualization at the top, playing the actual recorded call audio (real synthesized voices on both sides — the AI negotiator and the human billing rep). Include a play/pause control, a scrubber over the waveform, and a status indicator that reads "LIVE" (pulsing) during an active call or a static "Recorded" state for playback/replay mode.
- Directly below the player: a LARGE price ticker — the single biggest text element on the entire screen — showing the balance with a delta badge as it changes (e.g. "$4,287 → $3,875" with a coral down-arrow, then updating again to "$3,875 → $1,650").
- Below that: a scrolling transcript feed, with the line currently being spoken highlighted/synced to the audio playhead position. Show a realistic snippet of dialogue (a few lines) — the agent citing the duplicate charge, the rep conceding, the agent citing Medicare/Mercy's own price, the settlement ask.
- A vertical lever-ladder progress stepper (compact) showing the current negotiation step (e.g. "Line-item dispute → Benchmark anchor → Settlement ask," current step emphasized).
- A small AI-disclosure badge/indicator that lights up once disclosure has been given in the call.

### Right panel — the proof side
Technical content that never appears anywhere else in the product — this is what convinces a technical judge the system is real:
- A live event log, monospace type, timestamped, showing tool calls firing in real time as the call progresses — e.g.:
  ```
  14:32:07  get_benchmark(71046)
            → medicare: $438 · mrf_cash: $1,890
  14:32:19  report_lever_result(duplicate_charge, conceded)
            → next_move: benchmark_anchor
  14:33:02  log_quote($3,875)
  ```
  Design this to feel like a real system console — each entry timestamped, monospace, appearing in sequence.
- A statute/lever "arming" panel below or beside the log — a short list of negotiation levers (e.g. "Duplicate-charge dispute," "No Surprises Act," "§501(r) charity care," "Price benchmark"), each shown as a row that is either dormant (grey/muted) or armed (accent-colored, with its citation shown inline, e.g. "ARMED — Medicare $438 / Mercy cash $1,890").
- A small persistent status card showing a running honesty-audit counter, e.g. "0 unverified claims" — styled to stay visible and reassuring throughout, not just a final badge.
- A single logged line showing the exact disclosure moment, timestamped — e.g. "14:31:44 — Disclosed: AI advocate, calling on Maya's behalf, call recorded."

## Output expectations
Design two states of this same screen: (1) call in progress — both panels actively populating, ticker mid-transition, "LIVE" audio state; (2) call completed — waveform shows a finished/full scrubber, final price shown, right panel shows the complete tool-call log and honesty-audit badge reading "passed." Keep the visual language (chips, cards, mono type treatment) consistent with a warm, cash-themed, non-clinical brand — this should look like a confident fintech/ops tool, not a hospital dashboard.
