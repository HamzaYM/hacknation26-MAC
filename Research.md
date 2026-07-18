# The US Medical Billing System, End-to-End: A Design Brief for "The Negotiator" (Medical Bills Vertical)

## TL;DR
- **For a bill-lowering voice agent, the primary call target is the hospital/provider's billing or patient financial services (PFS) department — not the insurer.** The insurer is the correct target only when the leverage is a claim adjudication problem (denial, misapplied cost-sharing, network error, or a No Surprises Act violation). Design the Caller to route dynamically: insurer first when the EOB is wrong, provider first when the patient's balance is simply unaffordable or the bill contains errors.
- **The system's negotiation engine should be built on three stacked levers, applied in sequence: (1) error/coding disputes, (2) statutory rights (No Surprises Act balance-billing bans, 501(r) charity care for nonprofit hospitals, self-pay/Good Faith Estimate protections), and (3) price benchmarking (Medicare rates, FAIR Health, hospital price-transparency files).** Combining all three routinely yields 30–70% reductions on out-of-pocket balances, and charity care can eliminate 50–100%.
- **Your config schema must be keyed to CPT/HCPCS codes and DRGs, ingest the itemized bill AND the EOB as separate objects, and store a per-line "fair price band"** (typically expressed as a multiple of Medicare, e.g., 150–250%). The gap between the billed/chargemaster amount and this band is the negotiator's quantified ask.

## Key Findings

**1. The EOB and the bill are two different documents, and the gap between them is where most leverage lives.** The Explanation of Benefits comes from the insurer and is explicitly "not a bill"; the bill comes from the provider. The patient-responsibility figure on the EOB should match the provider's bill — when it doesn't, that is a first-order red flag. Your Estimator must capture both and reconcile them line by line.

**2. Chargemaster prices are largely fictional list prices.** Per Bai & Anderson, *Health Affairs* (June 2015), "Extreme Markup: The Fifty US Hospitals With The Highest Charge-To-Cost Ratios": "On average, U.S. hospital charges were 3.4 times the Medicare-allowable cost in 2012… These hospitals have markups approximately ten times their Medicare-allowable costs compared to a national average of 3.4 and a mode of 2.4." (The highest-markup facility, North Okaloosa Medical Center, FL, charged 12.6× cost; 49 of the top 50 were for-profit.) Insurers negotiate this down; uninsured/self-pay patients are the ones exposed to the full inflated number, which is precisely why self-pay discounts of 40–60% exist.

**3. Medicare is the universal benchmark.** Per RAND's Round 5.1 Hospital Price Transparency Study (published May 2024, updated December 2024), employers and private insurers paid on average 254% of what Medicare would have paid for the same services at the same facilities in 2022 (inpatient 254%, outpatient 279%, professional 184%), with state averages ranging from under 170% (Arkansas) to over 300% (CA, DE, FL, GA, NY, SC, WV, WI). Professional advocates anchor self-pay negotiations at 150–200% of Medicare. This makes Medicare rates the single most useful reference the system can compute.

**4. Nonprofit hospitals are legally constrained in what they can charge low-income patients.** Under IRS §501(r), a nonprofit hospital cannot charge a financial-assistance-eligible patient more than the "amounts generally billed" (AGB) to insured patients, and must screen for eligibility before "extraordinary collection actions." This is a hard legal lever, not a favor.

**5. The No Surprises Act removes entire categories of bills from the table.** Emergency care and out-of-network care delivered at in-network facilities (anesthesiology, radiology, pathology, etc.) cannot be balance-billed. For uninsured/self-pay patients, a Good Faith Estimate that is exceeded by $400+ triggers a formal dispute right.

## Details

### 1. The full flow, in correct sequence

1. **Care is delivered.** The provider records diagnoses (ICD-10 codes) and services (CPT/HCPCS codes; inpatient stays are grouped into a DRG).
2. **Charge capture → claim creation.** Charges are drawn from the hospital's **chargemaster** (the master list of gross charges — inflated list prices). A claim (electronic 837 file) is assembled.
3. **Clearinghouse scrubbing.** The claim routes through a clearinghouse that validates formatting. Technical failures are **rejections** (corrected and resubmitted within hours/days — no appeal needed) — distinct from denials.
4. **Payer adjudication.** The insurer verifies eligibility, checks coding, applies medical-necessity and policy rules, and decides: pay in full, pay reduced, pend, or deny. Adjudication historically takes ~30–45 days; timely-filing limits are commonly 90–180 days (Medicare up to 12 months). Denials are common: per KFF's "Claims Denials and Appeals in ACA Marketplace Plans in 2024" (March 2026), HealthCare.gov insurers denied 19% of in-network claims and 37% of out-of-network claims in 2024 (combined average ~20%), with in-network rates ranging 3%–36% across insurers — roughly 85 million in-network claims denied.
5. **The EOB is issued.** It shows: **billed amount** (chargemaster charge) → **allowed amount** (the negotiated/contracted rate) → **plan paid** → **patient responsibility** (deductible + coinsurance + copay + non-covered). The difference between billed and allowed is written off by in-network providers.
6. **The provider bills the patient** the patient-responsibility remainder. This should match the EOB.
7. **Patient reviews / disputes / negotiates.** Request an itemized bill (right to receive it, generally within 30 days). Reconcile against the EOB. Then apply error disputes, statutory rights, and price benchmarking.
8. **Escalation paths:** insurer claim reprocessing → internal appeal (typically 180 days to file) → external review; provider financial assistance / charity care application; lump-sum settlement; payment plan; and, if it goes to **collections**, debt-validation and settlement (often 25–50 cents on the dollar).

Key terminology to encode as first-class schema fields: chargemaster/gross charge, allowed amount, coinsurance (a %), copay (fixed $), deductible, out-of-pocket max, balance billing, EOB vs. itemized bill, DRG, CPT/HCPCS.

### 2. Who the agent actually calls

- **Provider billing / Patient Financial Services — the default target for lowering a balance.** Front-line reps have limited authority; the agent should explicitly ask for a **billing supervisor, financial counselor, or patient advocate/ombudsman**, who can authorize discounts and charity care.
- **Insurer — target when the leverage is adjudication.** Denials, misapplied deductible/coinsurance, in-network provider processed as out-of-network, out-of-pocket max not applied, coordination-of-benefits errors, or No Surprises Act violations. Here the fix is claim reprocessing or an appeal, and the provider genuinely cannot lower the patient's share until the insurer corrects the claim.
- **Both, in sequence** is common: fix the insurer's adjudication first (which may erase or shrink the balance), then negotiate the residual with the provider.
- **Collections agency** is a distinct playbook: the agent must first send a debt-validation request, then negotiate a lump-sum settlement; collectors cannot fix coding errors or grant charity care (must go back to the provider for that).

Who has authority to reduce a bill and under what circumstances: **uninsured/self-pay discounts** (routinely 40–60% off chargemaster; e.g., Med Center Health applies a 20% self-pay discount plus an additional 30% for attested uninsured patients, and 60% at one of its facilities); **financial assistance/charity care** (required of nonprofit hospitals under §501(r); many cover up to 300–400% of the Federal Poverty Level); **prompt-pay/lump-sum discounts** (commonly 10–30%, sometimes higher); **error disputes**; and **No Surprises Act balance-billing disputes**.

### 3. Data sources and building a "fair price benchmark"

- **Medicare reimbursement rates (CMS fee schedules):** the anchor. Compute the Medicare allowed amount for each CPT/DRG in the patient's locality; express the ask as a multiple (self-pay target ~150–200% of Medicare).
- **CMS Hospital Price Transparency machine-readable files (45 CFR Part 180):** every hospital must post a single MRF with gross charges, **discounted cash prices**, **payer-specific negotiated charges**, and de-identified min/max negotiated charges — keyed to CPT/HCPCS/DRG. As of the CY2026 rule, hospitals must encode actual dollar amounts (median plus 10th/90th percentile allowed amounts) rather than estimates, computed from EDI 835 remittance data over a 12–15 month lookback; enforcement began April 1, 2026. This lets the system cite the same hospital's own negotiated/cash price for the exact code.
- **FAIR Health** (fairhealthconsumer.org, free): an independent nonprofit holding the nation's largest commercial-claims database (over 49 billion claim records). Two benchmark families: **FH Charge Benchmarks** (billed charges) and **FH Allowed Benchmarks** (in-network negotiated amounts), reported by percentile and by "geozip" (first 3 digits of ZIP). States use specified FAIR Health percentiles (e.g., New York uses the 80th percentile of charges; Texas uses the 80th percentile of billed charges and 50th percentile of allowed amounts) in surprise-billing arbitration; the FH NSA Reference File supports federal No Surprises Act IDR/QPA calculations.
- **Healthcare Bluebook** and similar consumer tools for a quick fair-market cross-check.
- **How to fuse them:** for each line item, pull (a) Medicare rate, (b) FAIR Health allowed percentile for the geozip, (c) the hospital's own transparency-file cash/negotiated price, and compute a **fair-price band**. Flag any charge that exceeds the top of the band; the excess is the quantified negotiation target.

### 4. Common billing errors and red flags (the leverage list)

- **Duplicate charges** — same CPT/date billed twice (common at shift changes).
- **Upcoding** — a higher-complexity code than the service delivered (e.g., a Level 5 ER visit, CPT 99285, for a minor issue; a 15-minute visit billed as 99215).
- **Unbundling / NCCI violations** — separately billing components that should be one bundled code (e.g., a comprehensive metabolic panel, CPT 80053, split into individual tests; surgical prep billed separately; follow-up visits within a global surgical period billed separately).
- **Services not rendered / phantom billing** — charges for canceled tests, declined meds, or items absent from the clinical record.
- **Inflated supply/drug markups** — hospital supply/drug charges marked up many multiples over acquisition cost.
- **Balance-billing violations** under the No Surprises Act.
- **Math/processing errors** — bill doesn't match EOB, wrong quantities, wrong member ID, wrong service dates, deductible/out-of-pocket-max misapplied, preventive care billed as diagnostic.

How advocates identify them: request the itemized bill, cross-reference every CPT code against the EOB and the patient's medical record (patients have a federal right to their records, generally within 30 days), verify OR time against actual procedure duration, and demand correction (and, where insurance was affected, resubmission). Note on the widely-cited "up to 80% of medical bills contain errors" figure: this is an advocacy-industry estimate originating with Pat Palmer / Medical Billing Advocates of America, popularized after the 2013 TIME "Bitter Pill" story; the CFPB has been cited for a more conservative "up to 49%." Treat the range (roughly 49–80%) as product motivation, attributed to its sources, not as an established academic fact.

### 5. Regulations that shape strategy and script

- **No Surprises Act (effective Jan 1, 2022):** bans balance billing for (a) emergency services, (b) out-of-network ancillary providers at in-network facilities, and (c) out-of-network air ambulance. Patient owes only in-network cost-sharing. Ancillary providers (anesthesia, pathology, radiology, neonatology) cannot even ask patients to waive protections. Consent-to-waive requires a notice given ≥72 hours in advance. Uninsured/self-pay patients get a **Good Faith Estimate**; per CMS, "A patient-provider dispute resolution process is now available for uninsured (or self-pay) consumers who get a bill from a provider that's at least $400 more than the expected charges on the good faith estimate," and consumers "must start the dispute process within 120 calendar days," with a "$25 fee." Complaints: CMS No Surprises Help Desk, 1-800-985-3059. It is a federal floor; stronger state laws prevail. Does not apply to Medicare/Medicaid/TRICARE/VA (already protected). Enforcement penalties reach up to $10,000 per violation.
- **CMS Hospital Price Transparency Rule (45 CFR Part 180):** the compliance basis for demanding the hospital's own posted cash/negotiated price.
- **IRS §501(r) (nonprofit hospitals):** must maintain a written Financial Assistance Policy (FAP), widely publicize it (including on billing statements, in the ER, and in admissions areas), limit charges to FAP-eligible patients to **Amounts Generally Billed (AGB)** (computed via a look-back method or a prospective Medicare/Medicaid method), and make reasonable efforts to determine FAP eligibility before extraordinary collection actions. The FAP application deadline is generally at least 240 days from the first post-discharge bill. Failure can cost tax-exempt status (and a $50,000 excise tax for CHNA failures).
- **Credit-reporting changes:** Per the joint Equifax/Experian/TransUnion announcement (April 11, 2023), "medical collection debt with an initial reported balance of under $500 has been removed from U.S. consumer credit reports… now nearly 70 percent of the total medical collection debt tradelines… are removed." Paid-in-full medical collections were removed as of July 1, 2022, and the reporting delay for unpaid medical debt was extended from 6 months to 1 year. (Note: a 2025 CFPB attempt to ban all medical debt from credit reports was vacated by a federal court, so these industry changes — not the CFPB rule — govern.)

### 6. Negotiation scripts and levers (for the Caller/Closer)

The canonical advocate sequence, which maps cleanly to voice-agent states:
1. **Open + hold the account.** "I'm calling about account #___. Please place this account on hold / pause aging while I review it." Request a fully itemized bill with CPT codes, quantities, unit prices.
2. **Reach authority.** "Please connect me with a billing supervisor, financial counselor, or patient advocate who can adjust balances."
3. **Financial assistance first.** Ask whether the patient qualifies for the FAP/charity care and request the application — do this before negotiating, because it reframes the whole conversation.
4. **Dispute specific line items** with the error list above, citing code-by-code discrepancies against the EOB/record.
5. **Benchmark the price.** "Medicare pays $X for this code; FAIR Health's benchmark for this area is $Y; your own posted cash price is $Z. I'm asking you to adjust to a fair rate."
6. **Self-pay / prompt-pay discount.** "What is your self-pay discount? I understand many hospitals offer 40–60%."
7. **Lump-sum settlement.** "I can pay $___ today as payment in full. Can you submit this as a hardship settlement to your supervisor?" (Lump-sum discounts of 10–30% are common; combined with errors + charity care, total reductions of 50–86% are documented in published advocate case studies.)
8. **Payment plan fallback.** Insist on interest-free terms.
9. **Escalate** to written certified-mail disputes, state regulators, or the CMS No Surprises complaint line. Always get any agreement **in writing** before paying.

For collections accounts, the sequence changes: send a written debt-validation request first, then offer a lump-sum settlement (collectors commonly accept 25–50% of the balance), and require written confirmation that the remaining balance is forgiven before paying.

### 7. Existing services for process-design inspiration

- **Goodbill** — hospital-bill specialist; combines medical-coding experts with AI to audit bills and drafts formal negotiation letters; screens for 501(r) charity care; ~20% of savings, capped at $1,000. Publishes case reductions (e.g., a $3,620 bill cut to $542).
- **Resolve (resolvemedicalbills.com)** — dedicated advocate model; tiered 10–25% contingency (with a $249–499 deposit; handles collections; $5,000 minimum for collections cases); founder Braden Pan has stated savings are found in ~95% of disputes it takes on.
- **CareRoute** — multi-strategy (errors, charity care, insurer disputes, negotiation); 18–25% capped at $1,000; publishes free scripts/templates.
- **Dollar For** — nonprofit focused purely on charity-care applications (free; helps patients at ~300% FPL or below); publishes negotiation and settlement scripts.
- **Patient Advocate Foundation** (free case management, income-qualified) and **SHIP** (State Health Insurance Assistance Program, free Medicare counseling, 1-877-839-2675).
- **Medical Cost Advocate, Health Advocate (Union Plus, free to union members with a bill ≥$400).**
- Typical independent advocate economics: contingency of 25–35% of savings, or $100–350/hour, or flat fees $300–1,500. Red flags in the space: upfront fees with guaranteed results, or fees charged on the total bill rather than the savings.

## Recommendations

**Stage 1 — Estimator (intake).** Build two structured objects: `EOB` and `itemized_bill`, each an array of line items keyed by CPT/HCPCS (or DRG). Required fields per line: code, description, date_of_service, units, billed_amount, allowed_amount, plan_paid, patient_responsibility, place_of_service, provider_NPI, in_network_flag. Immediately compute an `eob_bill_reconciliation` diff. Capture patient context: insured vs. self-pay, household income and size (for FPL/501(r) screening), hospital nonprofit status, emergency vs. scheduled, and whether a Good Faith Estimate exists.

**Stage 2 — Benchmark engine.** For each line, populate a `fair_price_band` from three sources (Medicare rate, FAIR Health geozip percentile, hospital MRF cash/negotiated price). Store benchmarks as **configurable multiples of Medicare** (default self-pay target 150–200%; flag anything meaningfully above the ~254% commercial norm). Auto-generate a `red_flags` array (duplicate, upcode candidate, unbundle candidate via NCCI, phantom charge, balance-billing violation, EOB mismatch).

**Stage 3 — Caller routing logic.** Decision rule: if `eob_bill_reconciliation` shows an adjudication problem (denial, network error, cost-sharing misapplication, NSA violation) → call **insurer** first (reprocess/appeal). Else → call **provider PFS**. Always request itemized bill + account hold on the first provider call; always ask for a supervisor/financial counselor.

**Stage 4 — Closer negotiation ladder.** Encode the 9-step script as a state machine with fallbacks. Sequence levers as: errors → charity care/501(r) → statutory (NSA/self-pay) → benchmark-anchored price → self-pay/prompt-pay discount → lump-sum settlement → payment plan. Produce a ranked, evidence-backed report: per-line "billed vs. fair vs. achieved," the statutory/benchmark citation used, and the settlement secured in writing.

**Thresholds that change the strategy:**
- Bill in collections → switch to debt-validation + 25–50%-of-balance settlement track.
- Income ≤ ~200–400% FPL at a nonprofit → charity care becomes the lead lever (potential 50–100% elimination), not price negotiation.
- Emergency or in-network-facility ancillary out-of-network charge → NSA makes it non-negotiable/illegal; file a complaint rather than negotiate.
- Bill < ~$500 → lower ROI; medical debt under $500 is already off credit reports, so weight the effort accordingly.

## Caveats

- **The "80% of bills contain errors" statistic is an advocacy-industry estimate (Medical Billing Advocates of America), not a peer-reviewed or government figure, and reflects a self-selected sample of bills patients already suspected — present it as a range (≈49–80%) and attribute it.** Use it for product motivation, not as a hard claim in patient-facing reports.
- **On dispute success rates:** the best primary evidence (Duffy et al., *JAMA Health Forum*, Aug 2024) found that ~74% of people who reached out about a suspected billing mistake had it corrected and ~62% who negotiated got a price drop — but these rest on small subsamples (37 and 14 respondents respectively), so treat them as directionally encouraging, not precise.
- **Discount percentages are highly variable** by hospital, state, income, and whether payment is immediate. The ranges here are planning defaults, not guarantees; make every percentage a config parameter.
- **Voice-agent authorization is a legal/consent issue.** To speak with an insurer or provider on a patient's behalf, the agent needs a HIPAA-compliant authorization on file; build consent capture into the Estimator.
- **State law frequently overrides the federal floor** (e.g., ground-ambulance balance billing, California's Hospital Fair Pricing Act, stronger charity-care mandates in CA/IL/NY/MA). The config must be state-aware.
- **CMS transparency-file data quality is uneven** and the CY2026 dollar-amount requirements were still phasing in with enforcement beginning April 2026; treat MRF values as corroborating, not sole, evidence.
- Some cited percentages (self-pay discounts, settlement ranges) come from advocacy blogs and vendor pages; the primary-source anchors (RAND 254%, Bai/Anderson 3.4×, KFF denial rates, CMS $400/120-day, IRS §501(r) AGB, the 2023 credit-bureau changes) are the ones safe to hard-code.