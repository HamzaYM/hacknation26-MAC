# Haggl — Competitive Landscape & Beachhead Market Research

*Deep-research run, 2026-07-18 · 104 agents · 22 sources fetched · 104 claims extracted · 25 adversarially verified (3-vote) → 24 confirmed, 1 refuted. Claims below are tagged **[verified]** (survived 3-vote adversarial verification), **[extracted]** (pulled from a primary source by the pipeline but not put through the verification round), or **[direct fetch]** (single KFF lookup done after the run to close the Oklahoma/Wyoming gap).*

---

## 1. Competitive landscape

The US patient-side billing-support market splits into four camps. **Nobody currently offers an automated, low-cost negotiation agent for sub-$5,000 bills — which is where the majority of US medical debt actually sits** (KFF: 56% of debtors owe under $2,500; only ~25% owe more than $5,000). **[verified]**

| Player | Model | Pricing | Scale / outcomes (self-reported) | What it means for Haggl |
|---|---|---|---|---|
| **Resolve Medical Bills** | Human-expert negotiation | $5k–$15k bills: $249 deposit + **25% of savings**; >$15k: $499 deposit + **10% of savings**. **Hard $5,000 minimum.** | 70% success rate; avg. savings >60% of billed amount (own disclaimer: 0–100%, no independent audit) | The outcome bar to publicly beat. Its economics *require* big bills — it structurally abandons the sub-$5k majority. **[verified]** |
| **Goodbill** | Human medical coders review record vs. bill | **20% of realized savings, capped at $1,000**, free if no savings | Patient-facing page shows no AI/automation (third-party directories call it "AI-powered" internally — scope that claim carefully) | Closest pricing comp. The $1,000 cap means small bills are unprofitable for them too. **[verified]** |
| **Dollar For** | Free 501(c)(3) charity-care navigator: 6-question bilingual screener → auto-filled financial-assistance applications → human appeals | **Free** (FY2025 revenue $1.46M, ~97% donations) | **~$157.8M in bills eliminated** to date (~$55M in 2025 alone) | Not a competitor — a **channel partner / free-tier benchmark**. Charity-care elimination is the fallback path when negotiation fails. **[verified]** |
| **Included Health** (and Quantum Health etc.) | Employer-paid navigation; billing help bundled into 24/7 support | No consumer pricing; sells ">2:1 ROI year 1" to employers via total-cost-of-care | $2,100/steered referral, $19k avg expert-opinion savings — zero bill-reduction metrics | **Not competing for Haggl's consumer.** B2B category; ignore short-term, watch as future distribution channel. **[verified]** |
| **AI-native entrants** | — | — | **Granted Health** (ex-Medbill AI, founded 2023, **$16.25M raised** — Forerunner, RRE): free any-size bill reviews, insurance-claim focus. **CareRoute**: no minimum, no upfront cost. | The sub-$5k gap is **thinly contested, not empty**. Haggl enters as differentiated (live voice negotiation), not first. **[verified]** |

**Haggl's structural wedge:** the only player whose unit economics work on a $1,400 bill (the national median collections balance) — because the negotiator is an AI voice agent, not a human coder on 20–25% contingency. The live-call automation is the moat none of the above claim publicly.

---

## 2. Beachhead geography — where the debt is

Primary source: Urban Institute *Debt in America* (Aug 2025 credit-bureau panel, >10M records, published Nov 2025). National baseline: **3.2% of credit-record adults have medical debt in collections; median balance $1,448**. **[verified]**

### States (share of adults with medical collections, Aug 2025) **[verified]**

| Rank | State | Share | Median balance | vs. national |
|---|---|---|---|---|
| 1 | **Oklahoma** | **8.7%** | $1,645 | 2.7× |
| 2 | Wyoming | 8.5% | $2,380 | 2.7× |
| 3 | Tennessee | 7.9% | $1,505 | 2.5× |
| 4 | Texas | 7.6% | $1,566 | 2.4× |
| 5 | Georgia | 7.4% | $1,465 | 2.3× |
| — | Louisiana 6.8% · Nevada 6.9% (median **$2,028**) · Arkansas 6.3% | | | |

Ranking is stable: the 2023 vintage of the same panel had OK (10.1%) and WY (10.0%) as #1–2. **[verified]**

### Counties/metros — the debt is in mid-size metros, not the big cities **[verified, 2-1 on list completeness]**

| Metro (county) | Share | Note |
|---|---|---|
| **Odessa, TX** (Ector) | **20.0%** | highest found |
| **Amarillo, TX** (Potter) | 17.5% | |
| Hunt Co., TX (Greenville) | 17.5% | second-tier TX metros: Gregg 15.7%, Grayson 15.2%, Wichita 13.9%, Taylor 13.2% |
| **Casper, WY** (Natrona) | 13.2% | median $2,193 |
| **Memphis, TN** (Shelby) | 12.2% | |
| **Oklahoma City** (Oklahoma Co.) | **11.5%** | |
| Cheyenne, WY (Laramie) | 10.9% | median **$3,798** — best per-case economics found |
| **Fort Worth, TX** (Tarrant) | 10.6% | the volume anchor |
| *Contrast:* Atlanta (Fulton) 4.5% · Houston (Harris) 5.1% · Dallas 7.2% · Tulsa 4.8% · Nashville 5.9% | | |

**Data caveats [verified]:** credit-bureau data undercounts true debt (post-2022 reforms removed paid + sub-$500 collections; the visible population shrank from ~14% of consumers in Mar 2022 to ~5% in Jun 2023 holding ~$49.2B). Seven states with medical-debt credit-reporting bans (CA, CO, IL, …) are invisible to this metric. KFF's broader survey measure (2019–21 SIPP, self-reported) ranks SD 17.7%, MS 15.2%, NC 13.4%, WV 13.3%, **GA 12.7%** — so Georgia's true burden likely exceeds its collections number. TAM: **~20M adults owing ≥$220B** (negotiable-balance core); 41% of adults carry some medical/dental debt on the widest definition.

---

## 3. Nonprofit hospital density & legal leverage

The workflow's verification round left this question thin; the figures below are **[extracted]** from KFF/AHA beds-by-ownership (2024 AHA Annual Survey) plus one **[direct fetch]** to fill OK/TN/WY.

### Nonprofit bed share in candidate states (community-hospital beds per 1,000 population, 2024)

| State | Nonprofit | For-profit | Gov't | Total | **Nonprofit share** | 501(r) lever |
|---|---|---|---|---|---|---|
| USA | 1.60 | 0.36 | 0.32 | 2.28 | **~70%** | baseline |
| **Georgia** | 1.71 | 0.19 | 0.26 | 2.17 | **~79%** | strongest |
| **Oklahoma** | 1.59 | 0.63 | 0.45 | 2.67 | **~60%** | solid **[direct fetch]** |
| **Tennessee** | 1.52 | 0.71 | 0.36 | 2.60 | **~58%** | solid **[direct fetch]** |
| **Texas** | 0.95 | 0.86 | 0.31 | 2.13 | **~45%** | weak — less than half of TX capacity |
| **Wyoming** | 0.67 | 0.31 | 2.21 | 3.19 | **~21%** | **mostly unavailable** — government district hospitals dominate **[direct fetch]** |

> **Key strategic consequence:** Haggl has three levers with different coverage. **(a)** Billing-error detection and **(b)** Medicare-rate / posted-cash-price anchoring work at *any* hospital. **(c)** The 501(r) charity-care lever works only at nonprofits — ~79% of Georgia beds, ~60% of Oklahoma, ~45% of Texas, ~21% of Wyoming. Wyoming's stellar debt numbers (Casper 13.2%, Cheyenne median $3,798) therefore come with the weakest legal toolkit.

### The legal-leverage picture **[verified unless noted]**

- **501(r) is the federal floor everywhere:** every 501(c)(3) hospital must maintain a financial-assistance policy, limit charges, and follow billing/collections restrictions, facility-by-facility, on pain of losing tax exemption. **[extracted, IRS primary source]**
- **The unclaimed pot is huge but the number is advocacy math:** hospitals fail to distribute an estimated **$14B/yr** in available charity care (cite as *"Dollar For estimates"* — extrapolated from Form 990 Schedule H via one Maryland study). **[verified, medium confidence]**
- **Enforcement is demonstrably weak:** GAO (2020) found the IRS couldn't evidence community-benefit audits; TIGTA (2025) found exempt-hospital exam referrals dropped **98%** FY2022–24; exactly **one** 501(r) revocation has ever occurred. Leverage is therefore *patient-initiated* — which is precisely the service Haggl automates. **[verified, 2-1]**
- **State law adds nothing in the beachhead states — and that's a feature:** ~21 states exceed federal charity-care requirements and 11 tie it to licensure (CA, CO, IL, ME, MD, NV, NY, RI, SC, VT, WA; Maine adds a private right of action) — all low-debt states. The Medical Debt Policy Scorecard ranks **Tennessee 50th (worst), SC 49th, Texas 48th** on patient protections. **[extracted]** In OK/TX/TN/GA, Haggl's federal 501(r) + posted-price playbook isn't one lever among many — it's the *only* protection patients have, and no state statute constrains or duplicates the service.
- **Posted-price ammunition is unreliable:** PatientRightsAdvocate found only **21.1%** of hospitals fully compliant with the federal price-transparency rule (Nov 2024, *down* from 34.5% in Feb 2024). PRA publishes a state-by-state compliance dataset — pull it when picking target hospital systems. **[extracted]** Where files are deficient, fall back on Medicare-rate anchoring (always computable — this is Jay's CMS benchmark pipeline).

---

## 4. Step-by-step market-entry roadmap

Scoring logic: debt concentration × nonprofit-bed share (501(r) coverage) × absence of statutory/competitive interference × per-case balance economics.

### Phase 0 — Beachhead: **Oklahoma City** (now → first 500 negotiated bills)
**Why OKC wins the multiplication:** #1 state by collections share (8.7%, stable #1–2 since 2023) · Oklahoma County at 11.5% (2.5× Atlanta's Fulton) · **~60% nonprofit beds** so the 501(r) lever covers most bills (unlike TX at 45% or WY at 21%) · median balance $1,645 sits dead-center in the sub-$5k zone every contingency incumbent refuses · no state statute to navigate — federal playbook only · a real metro (~1.4M) with volume, unlike Odessa/Amarillo.

**Proof points to manufacture in OKC:**
1. **Automated sub-$5k settlements at scale** — the segment Resolve ($5k floor) and Goodbill ($1k fee cap) structurally can't serve. This is the headline metric no incumbent can match.
2. **Error-detection hit rate** on itemized bills (the demo's "4 seeded errors" → real-world rate).
3. **Anchor win rates**: how often Medicare-rate and posted-cash-price citations move the settlement on live calls — logged per call, per hospital system.
4. **Charity-care conversion**: % of users screened into full 501(r) elimination (the Dollar For pathway). Explore a formal **Dollar For partnership** — they're free, complementary (elimination vs. negotiation), and their screener → your negotiation is a natural funnel in both directions.
5. **Pricing:** undercut visibly — e.g., flat fee or ≤10% contingency, no minimum — against Resolve's 25% + $249 and Goodbill's 20%.

### Phase 1 — Texas mid-size-metro corridor
**Fort Worth/Tarrant (10.6%)** as the volume anchor, plus the extraordinary second tier: **Amarillo 17.5%, Odessa 20.0%**, Hunt/Gregg/Grayson/Wichita/Taylor counties (13–17.5%). Caveat: TX is only ~45% nonprofit beds → **target nonprofit systems by name** (use PRA's state compliance data + AHA ownership data to build the hospital-level hit list) and lean on the ownership-agnostic levers (errors, Medicare anchor, posted prices) at for-profits. Skip Houston/Dallas/Austin/San Antonio initially — half the debt intensity, maximum competitor visibility.

### Phase 2 — Memphis + Georgia
**Memphis/Shelby (12.2%)**: worst-protected state in the country (TN ranked 50th) = patients most exposed and most in need; ~58% nonprofit beds. **Georgia (~79% nonprofit — best 501(r) coverage of any high-debt state)**: enter via KFF-survey-hot secondary metros rather than Atlanta (Fulton is only 4.5% on collections data, but statewide survey prevalence is 12.7% — the debt is there, just less credit-visible).

### Phase 3 — Opportunistic Wyoming; then the broader Southeast
Cheyenne ($3,798 median) and Casper ($2,193) offer the **best per-case economics found anywhere** — but with ~21% nonprofit beds, run them as a remote, posted-price/Medicare-anchor play only; don't build the charity-care motion around them. Then Louisiana (6.8%), Arkansas (6.3%), Mississippi/SC/NC as survey-data targets.

### Explicitly defer
Strong-law, low-debt states (WA, OR, MD, CA — statutory protections already do part of Haggl's job) and credit-reporting-ban states (debt signal invisible for targeting; acquisition would need hospital-system partnerships instead).

---

## 5. Open questions the research could not close

1. **Regulatory exposure of the core product** *(most important)*: state debt-adjusting/settlement licensing statutes, HIPAA authorization mechanics for an AI agent, hospital policies on third-party/automated callers, and call-recording consent in two-party-consent states — none of this was verified. Oklahoma/Texas call-consent rules need checking before the first production call.
2. **Granted Health and CareRoute traction** — are they at scale in the sub-$5k segment already, making Haggl a fast-follower? ($16.25M into Granted says take this seriously.)
3. **Hospital-level (not state-level) targeting data** — per-facility 501(r) compliance history and PRA transparency scores for OKC systems specifically.
4. **Post-vacatur reporting landscape** (CFPB's Jan 2025 credit-reporting rule was vacated July 2025) — where medical debt stays credit-visible will keep shifting; acquisition strategy may need to move from credit-geography targeting toward hospital-system partnerships.

## Refuted in verification
- A claim over-specifying the Urban Institute 2025 dataset's panel methodology (1-2 vote) — the dataset's *contents* were independently confirmed by download; its methodology framing was not. Rankings above rely only on the confirmed contents.

## Key sources
Urban Institute *Debt in America* interactive map + 2025 county dataset · Peterson-KFF Health System Tracker (medical-debt burden brief) · KFF Health Care Debt Survey · CFPB *Recent Changes in Medical Collections* (Mar 2024) · resolvemedicalbills.com/how-we-work · goodbill.com/patients · dollarfor.org · includedhealth.com · KFF beds-by-ownership (AHA 2024) · Commonwealth Fund state medical-debt protections (Jul 2025) · Community Catalyst 50-state compendium · Medical Debt Policy Scorecard (i4j) · PatientRightsAdvocate compliance reports · IRS 501(r) guidance · GAO-20-679 · CB Insights (Granted Health)
