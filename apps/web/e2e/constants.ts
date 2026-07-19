// Shared fixture identifiers — mirrors apps/api/app/fixtures.py DEMO_CASE_ID.
// Single source of truth for the specs so a future ID change is a one-line
// edit instead of a grep-and-replace across the suite.
export const DEMO_CASE_ID = "00000000-0000-0000-0000-000000000001";

// The dossier's headline pair on Maya's fixture case (apps/api/app/fixtures.py):
// bill.patient_balance = 4287.0 (what the bill says she owes), and the
// eob_mismatch flag's evidence.eob = 3875.0 (what her insurer's EOB says she
// owes instead) — the two numbers the "central argument" is built on.
export const DEMO_BILL_BALANCE = "$4,287";
export const DEMO_EOB_TARGET = "$3,875";
