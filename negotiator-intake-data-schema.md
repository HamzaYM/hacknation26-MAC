# The Negotiator — Intake Data Schema
### Mapping the whiteboard user journey to what the system actually needs to collect

Your 5 steps are the right shape. The gap is that steps 1–2 as drawn ("onboarding/profile," "upload bill + EOB") capture *identity* and *documents*, but the agent can't actually place a compliant, effective call without several categories of data that don't show up on either document. Below is the full breakdown, organized by *when* it's collected and *why the agent needs it*.

---

## Step 1: Onboarding / Profile Setup — expand beyond "insurance + DOB + address"

This step needs to produce three distinct things, not one: **identity**, **authorization**, and **call-authentication credentials**. Each solves a different downstream problem.

### 1a. Patient identity (who is this)
| Field | Why the agent needs it |
|---|---|
| Full legal name | Must match provider/insurer records exactly |
| DOB | Universal identity verifier used by every billing office and insurer IVR |
| Current address | Verifier; also determines state law (interest rules, extra medical-debt credit protections in the ~15 states that have them) |
| Phone / email | For the patient's own notifications, not for the agent's outbound caller ID |
| Relationship to patient | Self / parent-of-minor / legal guardian / POA — determines whose authorization is legally required |
| SSN (full or last 4) | Frequently required by billing offices to locate the account and by financial-assistance applications for income verification |

### 1b. Authorization to act (the part most designs miss)
This is the single biggest real-world blocker for an autonomous caller, and it's not just a checkbox:
- **HIPAA authorization / Release of Information (ROI)** naming the agent/company as authorized to discuss PHI with the specific provider(s). Providers legally cannot discuss bill details with anyone — human or AI — without this on file.
- **Insurer "authorized representative" designation** — most insurers require the *patient* to personally call once (or submit a form) to add the agent as an authorized rep on the account *before* the agent can be discussed with on subsequent calls. This is a common real-world gap: **the intake flow needs to check whether this has been done, and if not, trigger it as a blocking pre-step**, not assume the HIPAA form alone covers insurer calls.
- **Designation of Authorized Representative (AOR) form** — specifically needed for No Surprises Act GFE disputes and CMS complaints.
- **Recorded consent acknowledgment** — patient's consent for the agent to record calls and to disclose it is an AI acting on their behalf (ties to the disclosure requirements we researched earlier).
- **Data-processing/privacy agreement** — standard consent for storing PHI and financial data.

Track each of these as a **status field** (not-started / submitted / confirmed / expired), because they have different completion times and some (insurer authorized-rep) can take days to process — this belongs on the same timeline-tracking system as the regulatory deadlines.

### 1c. Call-authentication credentials
Billing offices and insurer IVRs authenticate callers with a fixed, predictable set of challenge questions. Capture these once so every subsequent call can pass verification without user involvement:
- DOB, address, last 4 SSN (already have these)
- Patient account number(s) / guarantor number per provider
- Insurance member ID + group number
- Any provider-specific "verification PIN" the patient has set up
- Insurer member-services phone number (from the card — often different from the general customer service line)

---

## Step 2: Upload Medical Bill + EOB — what "structured" actually means

Uploading the documents isn't the deliverable — the deliverable (per the challenge doc's Estimator module requirement) is a **confirmed structured job spec**, reused verbatim across every call. Document parsing (OCR/vision) needs to extract:

**From the bill:**
- Facility name, address, nonprofit/for-profit status (determines whether §501(r) protections apply)
- Statement date / first post-discharge bill date (starts every regulatory clock)
- Due date
- Account number
- Line items: CPT/HCPCS codes, revenue codes, DRG (if inpatient), description, charge amount, date of service, rendering provider/department (to detect split-billed entities like radiology, anesthesia, ER physician group)
- Whether this is an itemized bill or a UB-04 (if not, that's the first call's job)

**From the EOB:**
- Claim number
- Billed amount / allowed amount / plan paid / patient responsibility, per line item
- Coinsurance, copay, deductible breakdown
- In-network vs. out-of-network status
- Denial reason codes, if any
- Payer name and claims-appeals phone number (often distinct from member services)

**Derived flags the system should compute immediately on parse:**
- EOB-vs-bill mismatch detected? (patient responsibility on EOB ≠ amount billed)
- Emergency or in-network-facility/out-of-network-provider scenario? (triggers No Surprises Act path)
- Missing itemization? (triggers "request itemized bill/UB-04" as call 1's objective before any negotiation call)

---

## Step 3: Proposed Action Plan + Ranged Savings Estimate — inputs the system needs, not the user

This step doesn't need *new* data from the patient — it needs the fair-price-band computation from our earlier research (Medicare rate + FAIR Health benchmark + hospital's own price-transparency MRF) plus a **historical outcomes database** the system builds over time: past negotiated results for similar CPT codes / facilities / payers, so the "ranged estimate" gets more accurate with volume. Worth flagging as its own data asset now, since it compounds in value.

---

## Step 4: "Ask for more info… we can increase chances by X% if you [provide Y]" — the confidence-boosting layer

This is a great instinct — treat missing data as a quantified opportunity cost rather than a binary gate. Fields that specifically move the needle, tied back to the tactics research:

| Missing data | Unlocks | Why |
|---|---|---|
| Household income + size | Charity-care / financial-assistance eligibility screening (typically 200–400% FPL) | §501(r) charity care alone can reach 50–100% reduction |
| Employment status | Hardship framing credibility | Supports the "financial hardship" narrative that measurably moves reps |
| Pay stubs / tax return | Completes a FAP application if pursuing charity care | 67% approval rate when aided vs. 29% baseline (Dollar For data) |
| Other household medical debt | Aggregation strategy across bills/facilities | Some FAP policies and settlement leverage consider total burden |
| Ability to pay a lump sum today, and how much | Enables the "I can pay $X today, settle as paid-in-full" lever | This tactic requires knowing real liquidity, not a guess |
| Max comfortable monthly payment | Payment-plan fallback terms | Needed if lump-sum settlement isn't viable |
| Secondary insurance / Medicaid / Medicare status | Coordination-of-benefits errors, additional coverage to bill | Common source of EOB/bill mismatches |

---

## Step 5: Next Steps / Notify / Payment Deadline — case-state fields, not intake fields

This step needs the system to *track*, not *collect*. Store per-case:
- Notification channel preference (SMS/email/call) and cadence
- Every regulatory deadline computed from the statement date: 120-day/240-day/30-day §501(r) windows (nonprofit only), provider-specific collections-referral policy, 30-day FDCPA validation window (once/if sold to a collector), 365-day credit-report grace period
- Call log: date, entity called, rep name/ID, reference number, outcome, next action, next scheduled callback
- Current escalation level reached (front-line → supervisor → financial counselor → written dispute → regulator)
- Structured terminal state per bill: resolved (amount) / payment plan active (terms) / documented decline (reason, date) / escalated

---

## Consolidated intake schema (illustrative JSON shape)

```json
{
  "patient": {
    "legal_name": "", "dob": "", "address": {}, "phone": "", "email": "",
    "relationship_to_patient": "self|guardian|poa",
    "ssn_last4": ""
  },
  "authorizations": {
    "hipaa_roi": {"status": "not_started|submitted|confirmed", "provider_ids": []},
    "insurer_authorized_rep": {"status": "not_started|pending|confirmed", "insurer": "", "confirmed_date": null},
    "aor_form": {"status": "not_applicable|submitted|confirmed"},
    "call_recording_consent": true,
    "data_processing_consent": true
  },
  "call_auth_credentials": {
    "provider_account_numbers": {}, "insurer_member_id": "", "insurer_group_number": "",
    "provider_verification_pins": {}
  },
  "insurance": {
    "payer_name": "", "member_services_phone": "", "appeals_phone": "",
    "plan_type": "", "network_status": ""
  },
  "bill": {
    "facility_name": "", "nonprofit_status": true, "statement_date": "", "due_date": "",
    "account_number": "", "is_itemized": false, "line_items": []
  },
  "eob": {
    "claim_number": "", "line_items": [], "denial_codes": []
  },
  "derived_flags": {
    "eob_bill_mismatch": false, "nsa_applicable": false, "missing_itemization": true
  },
  "financial_profile": {
    "household_income": null, "household_size": null, "employment_status": "",
    "other_medical_debt": null, "lump_sum_available": null, "max_monthly_payment": null,
    "secondary_coverage": ""
  },
  "case_state": {
    "regulatory_deadlines": {}, "call_log": [], "escalation_level": "",
    "notification_prefs": {"channel": "", "cadence": ""}
  }
}
```

## Sensitivity note
Everything under `patient`, `financial_profile`, and parts of `insurance`/`bill` is PHI and/or financial PII. This schema should get encryption-at-rest, strict access scoping per call session, and a retention/deletion policy — worth deciding now since it shapes storage architecture, not just the intake form.
