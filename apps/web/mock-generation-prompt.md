Generate high-fidelity static UI mocks for "Haggl" — a product that reads a user's medical bill, finds errors and legal leverage, calls the billing office as an AI voice agent, and negotiates the balance down. This is a 14-hour hackathon build (ElevenLabs "The Negotiator" challenge, medical-bills vertical) — mocks need to be presentable to judges and buildable by an engineering team in the remaining hours, so favor clarity and a strong, consistent design system over speculative complexity.

## Design system — follow exactly, no substitutions

**Brand personality:** warm, a little irreverent, financially-themed (cash motifs, not medical iconography — deliberately avoids looking like a hospital or law firm). Two volumes: the landing/marketing surface is bold and playful; the actual product (once someone's looking at their real balance) is calm and competent — same palette and type, restrained application.

**Color:**
- Background (product): `#FAF7F2` warm off-white
- Background (marketing/landing only): `#FBE9DD` warm blush
- Surface/card: `#FFFFFF`, muted surface `#F5F1EC`
- Text primary: `#1A1410` (warm black, never pure black)
- Text secondary: `#6B6058`
- Text tertiary: `#A69C91`
- Accent (coral): `#EF6B45`, hover `#D95A34`, tint `#FCE3D8` — used for CTAs, savings figures, positive/settled states, links. This is the ONLY "win" color — never use green for savings or positive movement.
- Flag/attention (amber): `#C98A2E`, tint `#F6E7CC` — used for flagged billing errors/findings. **Never use red for a billing error or finding** — red reads as alarm and the product's job is to feel reassuring, not scary.
- Destructive (red): `#C4483A` — reserved only for true destructive actions (delete a document, cancel), never for "we found an issue."
- Border: `#E8DDD3`

**Typography:**
- Display/headline font: Bricolage Grotesque (bold, rounded, chunky grotesque — use for page titles and hero text only, never body copy)
- Body/UI font: General Sans
- Monospace font: IBM Plex Mono — used specifically for dollar amounts, CPT codes, and reference numbers in evidence/citation contexts, to signal "this is a traceable fact"

**Shape and depth:** full pill radius (9999px) on all buttons, badges, and status chips. 16px radius on cards. Flat design — no shadows on the marketing surface; product surface gets exactly one subtle shadow tier for card hierarchy (`0 1px 2px rgba(26,20,16,0.06), 0 1px 8px rgba(26,20,16,0.04)`), never stacked or layered further.

**Component patterns to reuse across every screen:**
- Status chips: full pill, small caps-ish label — positive/settled state uses accent-tint background + accent text; flagged/finding state uses flag-tint background + flag text; neutral/pending uses muted-surface background + secondary text
- Cards: white surface, 16px radius, 24px padding, 1px border, the one shadow tier
- Primary button: coral pill fill, white text; secondary button: transparent with dark pill outline

## The product — five real screens, plus one demo-only screen

Design these as a connected desktop web app (primary surface), consistent nav/shell across screens 1–4 (a persistent sidebar or top nav with: Bills, Action Items, and the user's name/avatar). Use this recurring demo case throughout for realistic content — keep the numbers consistent across every screen:

**Demo case — "Maya," 31, Boston MA.** ER visit at Mercy General Hospital (nonprofit). Total billed $8,432, current patient balance $4,287 (was — see Bill Detail below, it should show progress: an active bill that's already been partially negotiated down to $3,875 after one resolved call, with $2,637 in further estimated savings still on the table). Four findings on the bill: (1) duplicate chest X-ray charge, CPT 71046, +$412; (2) upcoded ER visit level (billed 99285, should be 99283); (3) unbundled lab panel (CPT 80053 billed as separate component tests instead of one bundled code, ~$640 overcharge); (4) bill total doesn't match her insurance EOB by $412. Three billing entities involved: Mercy General Hospital (facility), Bay State Emergency Physicians, and a $980 lab bill already sent to a collections agency.

### Screen 1 — Onboarding
Multi-step or single-scroll form (your call on which reads cleaner): identity fields (name, DOB, phone, hospital account/member ID), three consent status chips shown as a mocked-but-honest state machine (HIPAA release, insurer authorized-representative, call-recording consent — each showing "pending/submitted/confirmed"), and a light financial-snapshot entry point (income band, household size — 2-3 fields max). One primary CTA at the bottom: "Continue to your bills." Keep this screen the most restrained/quiet of the five — it's necessary friction, not a moment to sell.

### Screen 2 — Bill List
Header shows an aggregate savings figure across all the user's bills in large coral display type — e.g. "$2,637 in estimated savings identified" — this is the single most important number on the page, make it unmissable. Below: a list/grid of bill cards, one per medical event, each showing: provider name, current balance (mono figure), a status chip (in progress / awaiting your input / settled), and a small preview of the top finding ("4 issues found" as an amber chip). Include an "upload a new bill" affordance (drag-drop card or button) integrated into the list, not buried in a menu.

### Screen 3 — Bill Detail (three tabs: Diagnosis / Plan / Call History)
This is the most content-dense screen — design all three tab states.

- **Diagnosis tab:** the big balance number at top (mono figure, large), with a "central argument" summary card above the fold — plain-language framing like "You're likely protected under the No Surprises Act, there's a billing error inflating this by $412, and Mercy is charging roughly 200% of the fair benchmark price for these services." Below that, a line-item table or stacked list of the four findings, each as an expandable card showing: the CPT code (mono), what's wrong, the dollar impact (mono, amber-flagged), and the evidence/citation backing it (e.g. "Medicare pays $438 for these codes; Mercy's own posted price is $2,633").
- **Plan tab:** a vertical chronological stepper — steps like "Request itemized bill" → "Dispute duplicate charge" → "Cite No Surprises Act protection" → "Negotiate settlement" → "Confirm in writing." The current/active step is visually emphasized (larger, accent-colored, expanded detail); completed steps are collapsed to a single line with a checkmark; future steps are collapsed and muted. Design both the "call in progress" state (a live status strip showing current call status and a price ticker) and the "no call active" state.
- **Call History tab:** a list of past calls, each row showing entity name, date, outcome status chip, and the amount delta if any (e.g. "$4,287 → $3,875" with a coral down-arrow). Each row expands to show key takeaways as plain bullets (winning lever used, reference number, rep name, next action) — all in mono for the factual bits, body font for the narrative bits. Include an audio-playback affordance on resolved calls.

### Screen 4 — Action Items
A list/queue of items needing the user's input, aggregated across all their bills, presented one-at-a-time (show the "focused single card" state, not a long scrollable form). Each card follows this exact 3-part structure — this is a specific, non-negotiable content pattern:
1. The ask, stated as a plain question (e.g. "What's your household income range?")
2. A "Why we're asking" line in secondary text (e.g. "Nonprofit hospitals must offer discounted care below certain income thresholds — this determines if you qualify.")
3. An "Unlocks" line in accent color naming the specific downstream effect, ideally with a number (e.g. "Could add charity-care eligibility to your case — potentially reduces this bill by 50–100%")
Followed by exactly one input control (never a multi-field form) and a "Next" affordance. Show a small progress indicator (e.g. "2 of 5") so the user knows the queue has an end.

### Screen 5 (bonus, clearly labeled separately) — War Room / Live Call view
This is a demo/judge-facing screen, not part of the everyday user product — it exists to prove the engineering is real, not scripted. It focuses on **ONE live call** (not three in parallel — the product already shows aggregate/per-entity status on Bill List and Bill Detail; repeating that here would be redundant). Design it with more visual energy than the calm product screens (readable from across a room during a live presentation), split into two side-by-side panels:

**Left panel — the human side (what this call sounds and reads like):**
- An audio player/waveform at the top, playing the actual recorded call audio (real ElevenLabs voices — both the negotiator agent and the counterparty), with a play/pause control and a pulsing "LIVE" indicator when the call is in progress vs. a static "recorded" state for playback. This is real audio, not just a transcript — the demo's point is that judges *hear* the negotiation happening, not just read about it.
- A LARGE price ticker with a delta badge below the player (biggest text element on the screen) — e.g. "$4,287 → $3,875" with a coral down-arrow.
- A scrolling transcript feed underneath, with the currently-playing line highlighted/synced to the audio position.
- A vertical lever-ladder progress stepper showing the current negotiation step, and an AI-disclosure indicator (small badge, lights up once disclosure has been given).

**Right panel — the proof side (what only judges see, never shown in the real product):**
- A live technical event log — tool calls appearing the instant they fire, e.g. `get_benchmark(71046) → Medicare $438, Mercy MRF cash $2,633`, timestamped, appearing *before* the corresponding line lands in the transcript on the left (this sequencing is the visual proof that numbers come from tools, not improvisation).
- A statute/lever "arming" panel — each lever (duplicate-charge dispute, §501(r) charity care, No Surprises Act, price benchmark) shown as a row that flips from grey/dormant to armed (accent-colored, with its citation) the moment the backend arms it.
- A running honesty-audit counter — e.g. "0 unverified claims" — staying visible and at zero through the call, styled as a small persistent status card, not just an end-of-call badge.
- A disclosure timestamp line — the exact moment "I'm an AI advocate calling on Maya's behalf" was said, shown as a logged, timestamped event.

Design one hero state (call in progress, both panels active and populating) and one completed state (audio player shows a finished waveform scrubber, right panel shows the full final tool-call log and a "passed" honesty-audit badge).

## Output expectations
Produce distinct, complete mockups for all five numbered screens above (Onboarding, Bill List, Bill Detail × 3 tab states, Action Items, plus the bonus War Room screen) at desktop width. Keep every recurring component (status chips, cards, buttons, the balance/price mono-figure treatment) pixel-consistent across screens — a judge or engineer should be able to tell instantly that these came from one design system, not five separate explorations.
