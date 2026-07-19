"""Generate Maya's demo bill + EOB PDFs — derived from the fixture line items.

SINGLE SOURCE OF TRUTH: apps/api/app/fixtures.py DEMO_LINE_ITEMS (+ demo_answer_key.json).
The PDFs are what the OpenAI-vision parser reads on camera; parse output must
reconcile exactly with the fixtures, so this script *derives* every line and
total from them and asserts the sums (8,432 / 4,287 / 3,875) before writing.

Run from repo root:  python3 data/demo_docs/generate_demo_pdfs.py  (needs fpdf2)

Seeded errors (per demo_answer_key.json):
  (a) duplicate 71046 — $412 billed twice, same date
  (b) upcode 99285 with low-acuity dx J06.9 (records support 99283)
  (c) unbundled CMP — 14 components instead of 80053
  (d) EOB mismatch — insurer adjudicated only ONE 71046 → EOB $3,875 vs bill $4,287
"""
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.fixtures import DEMO_JOB_SPEC, DEMO_LINE_ITEMS  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent

BILL = DEMO_JOB_SPEC["bill"]
TOTAL_BILLED = BILL["total_billed"]          # 8432.00
BALANCE = BILL["patient_balance"]            # 4287.00
EOB_RESP = DEMO_JOB_SPEC["eob"]["patient_responsibility_total"]  # 3875.00
INSURANCE_PAID = round(TOTAL_BILLED - BALANCE, 2)                # 4145.00
DOS = "06/02/2026"

# ── derive + verify against the answer key before drawing anything ────────
line_sum = round(sum(li["billed_amount"] for li in DEMO_LINE_ITEMS), 2)
assert line_sum == TOTAL_BILLED == 8432.00, f"fixtures drifted: lines sum to {line_sum}"
assert round(BALANCE - 412.00, 2) == EOB_RESP == 3875.00, "duplicate/EOB mismatch arithmetic broke"

# EOB adjudicates only ONE 71046 (error d) — drop the second occurrence
_seen_71046 = False
EOB_LINES = []
for li in DEMO_LINE_ITEMS:
    if li["cpt"] == "71046":
        if _seen_71046:
            continue
        _seen_71046 = True
    EOB_LINES.append(li)
EOB_BILLED = round(sum(li["billed_amount"] for li in EOB_LINES), 2)  # 8020.00

# Per-line patient share: proportional allocation of the $3,875, rounding fixed on the last line
shares = [round(li["billed_amount"] * EOB_RESP / EOB_BILLED, 2) for li in EOB_LINES]
shares[-1] = round(shares[-1] + (EOB_RESP - round(sum(shares), 2)), 2)


def money(x: float) -> str:
    return f"${x:,.2f}"


def generate_bill() -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "MERCY GENERAL HOSPITAL", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, "55 Blossom Street, Boston, MA 02114  ·  Tax ID 04-1234567  ·  CCN 220078", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "ITEMIZED STATEMENT", ln=True, align="C")
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 9)
    for label, val in [
        ("Patient:", "Maya Chen (DOB 03/14/1995)"),
        ("Account #:", BILL["account_number"]),
        ("Date of Service:", DOS),
        ("Statement Date:", "06/20/2026    Due: 07/20/2026"),
        ("Attending:", "Dr. R. Patel, MD (Bay State Emergency Physicians)"),
        ("Diagnosis:", "J06.9 - Acute upper respiratory infection"),
        ("Primary Insurer:", "Blue Cross Blue Shield of Massachusetts"),
    ]:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(32, 5, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, val, ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(10, 6, "#", border=1, fill=True)
    pdf.cell(20, 6, "CPT", border=1, fill=True)
    pdf.cell(84, 6, "Description", border=1, fill=True)
    pdf.cell(20, 6, "Date", border=1, fill=True)
    pdf.cell(10, 6, "Qty", border=1, fill=True, align="C")
    pdf.cell(24, 6, "Amount", border=1, fill=True, align="R")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for n, li in enumerate(DEMO_LINE_ITEMS, 1):
        pdf.cell(10, 4.5, str(n), border=1)
        pdf.cell(20, 4.5, li["cpt"], border=1)
        pdf.cell(84, 4.5, li["description"][:52], border=1)
        pdf.cell(20, 4.5, DOS, border=1)
        pdf.cell(10, 4.5, "1", border=1, align="C")
        pdf.cell(24, 4.5, money(li["billed_amount"]), border=1, align="R")
        pdf.ln()

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(124, 6, "")
    pdf.cell(20, 6, "Total Charges:", align="R")
    pdf.cell(24, 6, money(TOTAL_BILLED), align="R", ln=True)
    pdf.cell(124, 6, "")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(20, 6, "Insurance Paid:", align="R")
    pdf.cell(24, 6, f"-{money(INSURANCE_PAID)}", align="R", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(124, 7, "")
    pdf.cell(20, 7, "BALANCE DUE:", align="R")
    pdf.cell(24, 7, money(BALANCE), align="R", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, "Payment due within 30 days. Financial assistance may be available.", ln=True)
    pdf.cell(0, 4, "For questions: (617) 555-0100 or billing@mercygeneral.org", ln=True)
    pdf.cell(0, 4, "To apply for Financial Assistance: mercygeneral.org/fap or call (617) 555-0105", ln=True)

    out = OUT_DIR / "mercy_general_bill.pdf"
    pdf.output(str(out))
    print(f"Generated: {out} ({len(DEMO_LINE_ITEMS)} lines, total {money(TOTAL_BILLED)})")


def generate_eob() -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "EXPLANATION OF BENEFITS", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Blue Cross Blue Shield of Massachusetts", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, "P.O. Box 55007, Boston, MA 02205", ln=True, align="C")
    pdf.cell(0, 5, "THIS IS NOT A BILL", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 9)
    for label, val in [
        ("Member:", "Maya Chen"),
        ("Member ID:", "XWB-9284751-01"),
        ("Group:", "EMP-44021 (PPO Select 2500)"),
        ("Claim #:", DEMO_JOB_SPEC["eob"]["claim_number"]),
        ("Date Processed:", "06/15/2026"),
        ("Provider:", "Mercy General Hospital / Bay State Emergency Physicians"),
        ("Date of Service:", DOS),
    ]:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 5, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, val, ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(20, 5, "CPT", border=1, fill=True)
    pdf.cell(74, 5, "Description", border=1, fill=True)
    pdf.cell(24, 5, "Billed", border=1, fill=True, align="R")
    pdf.cell(24, 5, "Plan Paid", border=1, fill=True, align="R")
    pdf.cell(24, 5, "You Owe", border=1, fill=True, align="R")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for li, share in zip(EOB_LINES, shares):
        pdf.cell(20, 4.5, li["cpt"], border=1)
        pdf.cell(74, 4.5, li["description"][:46], border=1)
        pdf.cell(24, 4.5, money(li["billed_amount"]), border=1, align="R")
        pdf.cell(24, 4.5, money(round(li["billed_amount"] - share, 2)), border=1, align="R")
        pdf.cell(24, 4.5, money(share), border=1, align="R")
        pdf.ln()

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(94, 6, "TOTALS:")
    pdf.cell(24, 6, money(EOB_BILLED), align="R")
    pdf.cell(24, 6, money(round(EOB_BILLED - EOB_RESP, 2)), align="R")
    pdf.cell(24, 6, money(EOB_RESP), align="R")
    pdf.ln(9)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "SUMMARY OF YOUR RESPONSIBILITY", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for label, val in [
        ("Annual Deductible applied:", money(2500.00)),
        ("ER Copay:", money(250.00)),
        ("Coinsurance:", money(1125.00)),
    ]:
        pdf.cell(60, 5, label)
        pdf.cell(30, 5, val, align="R", ln=True)
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(60, 7, "YOUR TOTAL RESPONSIBILITY:")
    pdf.cell(30, 7, money(EOB_RESP), align="R", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, "NOTE: This is an explanation of how your claim was processed. The provider may bill you for the amount shown above.", ln=True)
    pdf.cell(0, 4, "If you believe this claim was processed incorrectly, contact Member Services at 1-800-555-BCBS within 180 days.", ln=True)
    pdf.cell(0, 4, "Remark: CPT 71046 (Chest X-ray) - second instance on the provider claim was denied as a duplicate charge (same CPT, same date).", ln=True)

    out = OUT_DIR / "bcbs_eob.pdf"
    pdf.output(str(out))
    print(f"Generated: {out} ({len(EOB_LINES)} lines, patient responsibility {money(EOB_RESP)})")


# ══════════════════════════════════════════════════════════════════════════
# Reusable, DETERMINISTIC renderers for the WS4 scenario suite
# (data/scenarios/generate.py). These take a fully-specified context dict and
# return PDF bytes with a FIXED creation date, so `generate.py --check`
# regenerates byte-identical artifacts. The legacy generate_bill/generate_eob
# above are left byte-stable (untouched) on purpose.
# ══════════════════════════════════════════════════════════════════════════
import datetime as _dt  # noqa: E402

# A single fixed timestamp for every scenario PDF — the only way fpdf2 output is
# byte-reproducible (it otherwise embeds `now` in /CreationDate + /ModDate).
FIXED_PDF_DATE = _dt.datetime(2026, 7, 18, 0, 0, 0, tzinfo=_dt.timezone.utc)


def _new_pdf() -> FPDF:
    pdf = FPDF()
    pdf.set_creation_date(FIXED_PDF_DATE)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    return pdf


def render_scenario_bill_pdf(ctx: dict) -> bytes:
    """Itemized hospital statement for one scenario. `ctx` keys: hospital_name,
    address, tax_id, ccn, patient, dob, account, dos, statement_date, due_date,
    payer, diagnosis, lines[{cpt,description,date_of_service,units,billed_amount}],
    total_billed, insurance_paid, balance."""
    pdf = _new_pdf()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, ctx["hospital_name"].upper(), ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"{ctx['address']}  ·  Tax ID {ctx['tax_id']}  ·  CCN {ctx['ccn']}",
             ln=True, align="C")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "ITEMIZED STATEMENT", ln=True, align="C")
    pdf.ln(3)

    for label, val in [
        ("Patient:", f"{ctx['patient']} (DOB {ctx['dob']})"),
        ("Account #:", ctx["account"]),
        ("Date of Service:", ctx["dos"]),
        ("Statement Date:", f"{ctx['statement_date']}    Due: {ctx['due_date']}"),
        ("Diagnosis:", ctx["diagnosis"]),
        ("Primary Insurer:", ctx["payer"]),
    ]:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(32, 5, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, val, ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(10, 6, "#", border=1, fill=True)
    pdf.cell(20, 6, "CPT", border=1, fill=True)
    pdf.cell(84, 6, "Description", border=1, fill=True)
    pdf.cell(20, 6, "Date", border=1, fill=True)
    pdf.cell(10, 6, "Qty", border=1, fill=True, align="C")
    pdf.cell(24, 6, "Amount", border=1, fill=True, align="R")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for n, li in enumerate(ctx["lines"], 1):
        pdf.cell(10, 4.5, str(n), border=1)
        pdf.cell(20, 4.5, li["cpt"], border=1)
        pdf.cell(84, 4.5, (li.get("description") or "")[:52], border=1)
        pdf.cell(20, 4.5, li.get("date_of_service") or ctx["dos"], border=1)
        pdf.cell(10, 4.5, str(li.get("units", 1)), border=1, align="C")
        pdf.cell(24, 4.5, money(li["billed_amount"]), border=1, align="R")
        pdf.ln()

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(124, 6, "")
    pdf.cell(20, 6, "Total Charges:", align="R")
    pdf.cell(24, 6, money(ctx["total_billed"]), align="R", ln=True)
    if ctx.get("insurance_paid"):
        pdf.cell(124, 6, "")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(20, 6, "Insurance Paid:", align="R")
        pdf.cell(24, 6, f"-{money(ctx['insurance_paid'])}", align="R", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(124, 7, "")
    pdf.cell(20, 7, "BALANCE DUE:", align="R")
    pdf.cell(24, 7, money(ctx["balance"]), align="R", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, "Payment due within 30 days. Financial assistance may be available.", ln=True)
    return bytes(pdf.output())


def render_scenario_eob_pdf(ctx: dict) -> bytes:
    """Explanation of Benefits for one scenario. `ctx` keys: payer,
    payer_address, member, member_id, group, claim, date_processed, provider,
    dos, lines[{cpt,description,billed_amount,plan_paid,patient_responsibility}],
    eob_billed, eob_plan_paid, eob_resp, remark."""
    pdf = _new_pdf()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "EXPLANATION OF BENEFITS", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, ctx["payer"], ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, ctx.get("payer_address", ""), ln=True, align="C")
    pdf.cell(0, 5, "THIS IS NOT A BILL", ln=True, align="C")
    pdf.ln(4)

    for label, val in [
        ("Member:", ctx["member"]),
        ("Member ID:", ctx.get("member_id", "")),
        ("Group:", ctx.get("group", "")),
        ("Claim #:", ctx.get("claim", "")),
        ("Date Processed:", ctx.get("date_processed", "")),
        ("Provider:", ctx["provider"]),
        ("Date of Service:", ctx["dos"]),
    ]:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 5, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, val, ln=True)
    pdf.ln(3)

    lines = ctx.get("lines") or []
    if lines:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(20, 5, "CPT", border=1, fill=True)
        pdf.cell(74, 5, "Description", border=1, fill=True)
        pdf.cell(24, 5, "Billed", border=1, fill=True, align="R")
        pdf.cell(24, 5, "Plan Paid", border=1, fill=True, align="R")
        pdf.cell(24, 5, "You Owe", border=1, fill=True, align="R")
        pdf.ln()
        pdf.set_font("Helvetica", "", 7)
        for li in lines:
            pdf.cell(20, 4.5, li["cpt"], border=1)
            pdf.cell(74, 4.5, (li.get("description") or "")[:46], border=1)
            pdf.cell(24, 4.5, money(li["billed_amount"]), border=1, align="R")
            pdf.cell(24, 4.5, money(li.get("plan_paid") or 0.0), border=1, align="R")
            pdf.cell(24, 4.5, money(li.get("patient_responsibility") or 0.0), border=1, align="R")
            pdf.ln()
        pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(60, 7, "YOUR TOTAL RESPONSIBILITY:")
    pdf.cell(30, 7, money(ctx["eob_resp"]), align="R", ln=True)

    if ctx.get("remark"):
        pdf.ln(3)
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 4, f"Remark: {ctx['remark']}")
    return bytes(pdf.output())


if __name__ == "__main__":
    assert round(2500.00 + 250.00 + 1125.00, 2) == EOB_RESP, "summary components != 3875"
    generate_bill()
    generate_eob()
    print("\nDone. Derived from apps/api/app/fixtures.py — parse output reconciles by construction.")
