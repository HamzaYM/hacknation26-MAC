# Prompt for Design Agent

I'm attaching a research brief titled **"The Negotiator: End-to-End Design Brief for a Medical Bill-Lowering Voice Agent."** It's the reference document for a hackathon build (Hack-Nation × ElevenLabs, "The Negotiator" challenge — a voice-agent system that calls, compares, and negotiates medical bills on a patient's behalf).

I need you to turn this into a **visual, workflow-driven document** — not a condensed summary. Please read the entire attached document carefully and treat every section, statistic, threshold, and citation as required content. Do not skim, paraphrase away detail, or drop anything to save space — if something doesn't fit as a diagram, put it in a labeled reference panel, but keep it in the document somewhere.

## What the document needs to contain

Structure it around these sections, each built as its own visual:

**1. Overview panel**
The TL;DR and "Why this matters" framing from the source doc — the problem (opaque medical pricing, EOB/bill mismatches), the opportunity, and the core thesis (three-lever negotiation stack).

**2. End-to-end patient billing journey (swim-lane workflow)**
A swim-lane diagram with three lanes — **Patient**, **Provider**, **Insurer** — showing the full sequence from care delivery through resolution:
care delivered → charge capture (chargemaster) → claim creation (837 file) → clearinghouse scrubbing (rejection vs. denial branch) → payer adjudication → EOB issued (billed → allowed → plan paid → patient responsibility) → provider bills patient → patient reviews/reconciles EOB vs. itemized bill → dispute/negotiate → escalation paths (insurer appeal / provider financial assistance / lump-sum settlement / payment plan / collections).
Label every node with the correct terminology (chargemaster, allowed amount, coinsurance, copay, deductible, balance billing, DRG, CPT/HCPCS) exactly as defined in the source doc — include a small glossary callout if needed.

**3. "Who does the agent call?" decision tree**
A branching flowchart starting at "EOB vs. bill reconciliation" and routing to one of: **Insurer** (denial / misapplied cost-sharing / network error / NSA violation → reprocess or appeal), **Provider PFS** (balance is simply unaffordable, or bill contains errors → request itemized bill, ask for supervisor/financial counselor), or **Collections** (account already placed there → debt validation first, then settlement). Show that insurer-first and provider-first can chain sequentially.

**4. Three-lever negotiation stack (layered diagram)**
Visualize the stacked levers in the order they should be applied: **(1) Error/coding disputes → (2) Statutory rights (No Surprises Act, §501(r) charity care, self-pay/Good Faith Estimate protections) → (3) Price benchmarking (Medicare, FAIR Health, hospital price-transparency files).** Note that combining all three routinely yields 30–70% reductions, and charity care alone can reach 50–100%.

**5. Fair-price-band computation (data-fusion diagram)**
Show three inputs feeding one output per CPT/HCPCS/DRG line item: Medicare fee-schedule rate, FAIR Health allowed-benchmark percentile (by geozip), and the hospital's own CMS price-transparency MRF (cash/negotiated price) → combined into a **fair price band** (self-pay target default: 150–200% of Medicare; commercial norm flagged above ~254% per RAND). Include the RAND and Bai/Anderson figures as source annotations on this diagram (254% of Medicare on average in 2022; historic 3.4x cost markup, up to 12.6x at outlier hospitals).

**6. Red-flag / error-detection checklist**
A checklist-style workflow of what the system scans for on every line item: duplicate charges, upcoding, unbundling/NCCI violations, phantom charges, inflated supply/drug markups, balance-billing violations, EOB/bill mismatches, math errors. Include the error-rate caveat as a footnote (advocacy-industry estimate of ~49–80%, not peer-reviewed — attribute, don't state as fact).

**7. Regulatory landscape reference panel**
A compact reference (table or icon grid, not necessarily a flow) covering: No Surprises Act (bans, GFE dispute right — $400 threshold, 120-day window, $25 fee), CMS Hospital Price Transparency Rule (MRF requirements, CY2026 dollar-amount mandate, enforcement date), IRS §501(r) (FAP, Amounts Generally Billed, 240-day application window), and the 2023 credit-bureau changes (medical debt under $500 removed, paid collections removed, 1-year reporting delay).

**8. Negotiation script state machine**
A 9-step flowchart with fallback branches, following the source doc's sequence exactly: open + hold account → reach authority (supervisor/financial counselor) → financial assistance screening → line-item dispute → price benchmarking ask → self-pay/prompt-pay discount ask → lump-sum settlement offer → payment-plan fallback → escalation (written dispute / regulator / CMS complaint line). Show the collections-specific variant (debt validation → settlement offer → written forgiveness confirmation) as a branch off this same diagram.

**9. System build roadmap (mapped to the three hackathon modules)**
A 4-stage roadmap: **Stage 1 Estimator** (EOB + itemized-bill structured objects, reconciliation diff, patient context capture) → **Stage 2 Benchmark engine** (fair-price-band + red-flags computation) → **Stage 3 Caller routing** (the decision-tree logic from section 3) → **Stage 4 Closer negotiation ladder** (the state machine from section 8, producing the ranked evidence-backed report). Note which hackathon module (Estimator / Caller / Closer) each stage corresponds to.

**10. Threshold rules table**
The conditions that change strategy, as a decision table: bill in collections → debt-validation track; income ≤200–400% FPL at nonprofit → lead with charity care; emergency/in-network-facility-ancillary-out-of-network → NSA makes it non-negotiable, file a complaint instead; bill under ~$500 → lower-priority (already off credit reports).

**11. Competitive landscape table**
Goodbill, Resolve, CareRoute, Dollar For, Patient Advocate Foundation, SHIP, Medical Cost Advocate/Health Advocate — with their model, fee structure, and specialty, exactly as described in the source doc.

**12. Caveats & sourcing appendix**
Reproduce the full "Caveats" section from the source document verbatim in a clearly labeled appendix — including which statistics are safe to hard-code (RAND 254%, Bai/Anderson 3.4x, KFF denial rates, CMS $400/120-day rule, IRS §501(r) AGB, 2023 credit-bureau changes) versus which are directional/advocacy estimates (error-rate range, dispute-success rates from the small-sample JAMA Health Forum study, discount percentages).

## Requirements

- **Every percentage, dollar threshold, day count, and named statistic in the source document must appear somewhere in the output**, attached to the correct diagram or panel. Do not average, round, or drop any of them.
- **Preserve attributions and caveats** — where the source document flags a number as an estimate, an advocacy-industry figure, or based on a small sample, carry that qualifier into the visual (as a footnote, asterisk, or tooltip) rather than presenting it as settled fact.
- **Use the source document's own terminology** (chargemaster, allowed amount, geozip, AGB, GFE, DRG, CPT/HCPCS, etc.) instead of simplifying it.
- Format: a single cohesive document combining swim-lane/flowchart diagrams for the process sections (2, 3, 4, 5, 8, 9) with tables/reference panels for the static-reference sections (1, 6, 7, 10, 11, 12).
- This will be used both as an internal engineering reference for building the voice-agent system and as a walkthrough for hackathon judges — so it should be legible at a glance but hold up to close reading.

I'll attach the full source document alongside this prompt — pull every detail from it.
