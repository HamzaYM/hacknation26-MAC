# Haggl — Design System
**Owner: Susy.** Reference this file for all visual decisions in `apps/web/`. If a component doesn't fit a pattern below, ask before improvising — the goal is one coherent identity across five screens built by however many hands touch this repo.

## Brand personality

Haggl is the friend who's annoyingly good at winning arguments with billing departments on your behalf. Warm, a little irreverent, financially-themed (cash motifs, not medical iconography — we deliberately don't look like a hospital or a law firm).

**Two volumes of the same identity:**
- **Marketing** (public landing page) — bold, funny, confident. Loud accent color, big lowercase display type, playful illustration.
- **Product** (the actual app — Onboarding, Bill List, Bill Detail, Action Items, War Room) — same palette and type family, but restrained. Once someone's looking at their real balance, the jokes stop and competence takes over.

**Emotional job, by surface:**
- Marketing → *"this could actually work, and it doesn't feel like every other healthcare product"*
- Product → *"relieved — someone competent is handling this"*

---

## Color

| Token | Hex | Usage |
|---|---|---|
| `--bg-marketing` | `#FBE9DD` | Landing page background only |
| `--bg-product` | `#FAF7F2` | App background — same warm family, quieter |
| `--bg-surface` | `#FFFFFF` | Cards, panels |
| `--bg-surface-muted` | `#F5F1EC` | Nested panels, table stripes |
| `--text-primary` | `#1A1410` | Headings, body — warm black, never pure `#000` |
| `--text-secondary` | `#6B6058` | Supporting text, labels, metadata |
| `--text-tertiary` | `#A69C91` | Placeholders, disabled, timestamps |
| `--accent` | `#EF6B45` | CTAs, savings figures, positive/settled states, links |
| `--accent-hover` | `#D95A34` | Hover/active on accent elements |
| `--accent-tint` | `#FCE3D8` | Accent-colored chip backgrounds |
| `--flag` | `#C98A2E` | "We found an issue" chips — amber, not red |
| `--flag-tint` | `#F6E7CC` | Flag chip background |
| `--destructive` | `#C4483A` | True destructive actions only (remove document, cancel) |
| `--border` | `#E8DDD3` | Dividers, card edges, input borders |

**Two rules that are easy to violate under deadline pressure — don't:**
1. **Never use red/`--destructive` for a flagged billing error.** Red is alarm; a user staring at a scary balance doesn't need more of it. Findings (duplicate charge, upcode, etc.) always use `--flag` (amber). Destructive red is reserved for irreversible actions like deleting an uploaded document.
2. **Savings/positive movement is always `--accent` (coral), never green.** Coral is already the brand's "win" color from the landing page (the underline on "match"). Introducing green splits brand recall in two.

---

## Typography

- **Display:** [Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque) (Google Fonts) — headline instrument only, never body copy, never below H3 size.
- **Body/UI:** [General Sans](https://www.fontshare.com/fonts/general-sans) (Fontshare, free) — everything else.
- **Mono:** [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) — reference numbers, CPT codes, dollar amounts in evidence/citation contexts. Signals "traceable fact," matters for the Bill Detail trust job.

| Role | Size | Weight | Line height | Tracking | Usage |
|---|---|---|---|---|---|
| Marketing display | 64px | 800 | 1.02 | -0.01em | Landing hero only, lowercase |
| H1 | 32px | 700 | 1.15 | -0.01em | Page titles (balance amounts, etc.) |
| H2 | 22px | 600 | 1.25 | 0 | Section headings, tab labels |
| H3 | 17px | 600 | 1.35 | 0 | Card titles |
| Body | 16px | 400 | 1.6 | 0 | Main content |
| Small | 14px | 400 | 1.5 | 0 | Labels, metadata, secondary copy |
| Tiny | 12px | 500 | 1.4 | 0.02em | Badges, tags, timestamps |
| Mono figure | 15px | 500 | 1.4 | 0 | Amounts, CPT codes, reference numbers |

---

## Spacing (4px base)

| Token | Value |
|---|---|
| `--space-xs` | 4px |
| `--space-sm` | 8px |
| `--space-md` | 16px |
| `--space-lg` | 24px |
| `--space-xl` | 32px |
| `--space-2xl` | 48px |
| `--space-3xl` | 64px |

Marketing can use `2xl`/`3xl` liberally. Product screens live mostly in `sm`–`lg` — over-spacing a financial dashboard starts to feel like it's hiding something.

## Radius

| Context | Value |
|---|---|
| Buttons, pills, badges | `9999px` (full pill, everywhere) |
| Inputs | `10px` |
| Cards, panels | `16px` |
| Modals/sheets | `20px` |

## Elevation

Flat, one exception. Marketing: no shadows at all — depth comes from the color-block CTA and illustration layer. Product: one shadow tier for card hierarchy, never stacked:
```css
--shadow-card: 0 1px 2px rgba(26,20,16,0.06), 0 1px 8px rgba(26,20,16,0.04);
```

---

## Components

**Buttons**
- Primary: `--accent` fill, white text, full pill, hover → `--accent-hover`
- Secondary: transparent, 1.5px `--text-primary` border, full pill
- Destructive: `--destructive` fill, white text — delete/cancel only

**Status chips** (bill status, flag type, outcome type) — full pill, Tiny type:
- Positive/settled → `--accent-tint` bg / `--accent` text
- Finding/flag → `--flag-tint` bg / `--flag` text
- Neutral/pending → `--bg-surface-muted` bg / `--text-secondary` text

**Cards** — `--bg-surface`, 16px radius, `lg` padding, 1px `--border`, `--shadow-card`. Color lives in the chips and numbers inside, not the card frame.

**Action Item card** — fixed 3-part structure, always, no exceptions:
```
[The ask — Body, --text-primary]
"What's your household income range?"

Why we're asking · [Small, --text-secondary]
"Nonprofit hospitals must offer discounted care below certain
income thresholds — this determines if you qualify."

Unlocks · [Small, --accent text]
"Could add charity-care eligibility to your case —
potentially reduces this bill by 50–100%"

[ONE input control. Never a multi-field form.]
```
Pull the "Unlocks" dollar/percent figure from the same benchmark data already computed for Bill Detail — never hand-write a vague "this helps." If no dollar figure is computable, name the mechanism instead ("lets us verify you weren't billed out-of-network").

**Inputs** — 1px `--border`, 10px radius, `--accent` border on focus (no glow — flat identity stays flat), `--text-tertiary` placeholder. One question per screen in the Action Items flow.

---

## Motion

- **Marketing:** staggered hero entrance (60–100ms offsets), gentle continuous float on background illustrations (translateY, 4–6s ease-in-out loop), decorative only — never on interactive elements.
- **Product:** restrained. 150ms ease-out hovers, 200ms state changes, 250ms slide+fade on tab switches. No bounce, no overshoot.
- **Price-change moment** (a call updates the balance): number does a brief scale 110%→100% over 200ms with an `--accent-tint` color flash through. The one place product is allowed a little physicality — it's the payoff moment.

---

## What to avoid

- No floating cash illustrations inside the product — marketing-only device.
- No red for flagged billing errors — amber only; red is destructive-actions-only.
- No compound/multi-field forms in Action Items — one question, one input, one "why," always.
- No shadow-stacking in product UI — one elevation tier, full stop.
- No `Inter`/`Arial`/system-font fallback as the primary look — the font stack below is the whole point.

---

## CSS variables (drop into `globals.css`)

```css
:root {
  /* color */
  --bg-marketing: #FBE9DD;
  --bg-product: #FAF7F2;
  --bg-surface: #FFFFFF;
  --bg-surface-muted: #F5F1EC;
  --text-primary: #1A1410;
  --text-secondary: #6B6058;
  --text-tertiary: #A69C91;
  --accent: #EF6B45;
  --accent-hover: #D95A34;
  --accent-tint: #FCE3D8;
  --flag: #C98A2E;
  --flag-tint: #F6E7CC;
  --destructive: #C4483A;
  --border: #E8DDD3;

  /* spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;
  --space-3xl: 64px;

  /* radius */
  --radius-pill: 9999px;
  --radius-input: 10px;
  --radius-card: 16px;
  --radius-modal: 20px;

  /* elevation */
  --shadow-card: 0 1px 2px rgba(26,20,16,0.06), 0 1px 8px rgba(26,20,16,0.04);

  /* type */
  --font-display: "Bricolage Grotesque", ui-sans-serif, sans-serif;
  --font-body: "General Sans", ui-sans-serif, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
}
```

---

## Product IA (for context — see PRD §11 for the demo-only War Room spec)

Five screens: **Onboarding → Bill List → Bill Detail (tabs: Diagnosis / Plan / Call History) → Action Items**, plus **War Room** kept separate as a judge/demo-only live-call spectator view (not part of the real user product). Full screen-by-screen content spec lives in team chat history — ask Susy if you need the detail before it's written up as its own doc.
