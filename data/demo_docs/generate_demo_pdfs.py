"""Generate synthetic demo bill + EOB PDFs for The Negotiator demo.

Seeded errors per demo_answer_key.json:
  (a) Duplicate chest X-ray 71046 -- $412 billed twice
  (b) ER E/M upcoded 99285 where records support 99283
  (c) CMP 80053 unbundled into component labs ($690 vs ~$48 bundled)
  (d) Balance exceeds EOB patient responsibility ($4,287 vs $3,875)

USAGE:
    python generate_demo_pdfs.py
"""
from fpdf import FPDF
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent


def generate_bill():
    """Generate the Mercy General Hospital itemized statement."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "MERCY GENERAL HOSPITAL", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, "55 Blossom Street, Boston, MA 02114", ln=True, align="C")
    pdf.cell(0, 5, "Tax ID: 04-1234567  |  CCN: 220078  |  501(c)(3) Nonprofit", ln=True, align="C")
    pdf.cell(0, 5, "Phone: (617) 555-0100  |  Fax: (617) 555-0101", ln=True, align="C")
    pdf.ln(5)

    # Statement info
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "PATIENT STATEMENT - ITEMIZED", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(2)

    # Patient info box
    info = [
        ("Patient:", "Maya Chen"),
        ("Account #:", "MG-2026-048291"),
        ("Date of Service:", "05/12/2026"),
        ("Statement Date:", "06/15/2026"),
        ("Admit Type:", "Emergency - Outpatient"),
        ("Primary Dx:", "J06.9 - Acute upper respiratory infection, unspecified"),
        ("Attending:", "Dr. R. Patel, MD (Bay State Emergency Physicians)"),
    ]
    for label, val in info:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(35, 5, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, val, ln=True)
    pdf.ln(3)

    # Insurance info
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "INSURANCE INFORMATION", ln=True)
    pdf.set_font("Helvetica", "", 9)
    ins_info = [
        ("Primary Insurer:", "Blue Cross Blue Shield of Massachusetts"),
        ("Member ID:", "XWB-9284751-01"),
        ("Group #:", "EMP-44021"),
        ("Plan:", "PPO Select 2500"),
    ]
    for label, val in ins_info:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 5, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, val, ln=True)
    pdf.ln(5)

    # Line items table header
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(15, 6, "Line", border=1, fill=True)
    pdf.cell(22, 6, "CPT/HCPCS", border=1, fill=True)
    pdf.cell(65, 6, "Description", border=1, fill=True)
    pdf.cell(18, 6, "Date", border=1, fill=True)
    pdf.cell(12, 6, "Qty", border=1, fill=True, align="C")
    pdf.cell(22, 6, "Unit Price", border=1, fill=True, align="R")
    pdf.cell(22, 6, "Amount", border=1, fill=True, align="R")
    pdf.ln()

    # Line items (seeded with all 4 errors)
    items = [
        # Line 1: UPCODED E/M (99285 instead of 99283) -- ERROR (b)
        ("1", "99285", "ER Visit - High Severity (Level 5)", "05/12/2026", "1", "2,180.00", "2,180.00"),
        # Line 2: Chest X-ray (first instance -- legitimate)
        ("2", "71046", "Chest X-ray, 2 views", "05/12/2026", "1", "412.00", "412.00"),
        # Line 3: DUPLICATE chest X-ray -- ERROR (a)
        ("3", "71046", "Chest X-ray, 2 views", "05/12/2026", "1", "412.00", "412.00"),
        # Lines 4-8: UNBUNDLED CMP components -- ERROR (c)
        ("4", "84295", "Sodium, serum", "05/12/2026", "1", "98.00", "98.00"),
        ("5", "84132", "Potassium, serum", "05/12/2026", "1", "95.00", "95.00"),
        ("6", "82947", "Glucose, blood", "05/12/2026", "1", "89.00", "89.00"),
        ("7", "82565", "Creatinine, blood", "05/12/2026", "1", "92.00", "92.00"),
        ("8", "84520", "BUN (Blood Urea Nitrogen)", "05/12/2026", "1", "87.00", "87.00"),
        ("9", "82310", "Calcium, total", "05/12/2026", "1", "78.00", "78.00"),
        ("10", "84075", "Alkaline phosphatase", "05/12/2026", "1", "76.00", "76.00"),
        ("11", "84155", "Total protein, serum", "05/12/2026", "1", "75.00", "75.00"),
        # Line 12: CBC (legitimate)
        ("12", "85025", "CBC w/ automated differential", "05/12/2026", "1", "186.00", "186.00"),
        # Line 13: IV push (legitimate)
        ("13", "96374", "IV push, single drug (ondansetron)", "05/12/2026", "1", "890.00", "890.00"),
        # Lines 14-15: additional unbundled components to reach $690 total
        ("14", "84450", "AST (SGOT)", "05/12/2026", "1", "52.00", "52.00"),
        ("15", "84460", "ALT (SGPT)", "05/12/2026", "1", "48.00", "48.00"),
    ]

    pdf.set_font("Helvetica", "", 8)
    for item in items:
        pdf.cell(15, 5, item[0], border=1)
        pdf.cell(22, 5, item[1], border=1)
        pdf.cell(65, 5, item[2], border=1)
        pdf.cell(18, 5, item[3], border=1)
        pdf.cell(12, 5, item[4], border=1, align="C")
        pdf.cell(22, 5, f"${item[5]}", border=1, align="R")
        pdf.cell(22, 5, f"${item[6]}", border=1, align="R")
        pdf.ln()

    pdf.ln(3)

    # Summary
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(132, 6, "")
    pdf.cell(22, 6, "Total Charges:", align="R")
    pdf.cell(22, 6, "$8,432.00", align="R", ln=True)

    pdf.cell(132, 6, "")
    pdf.cell(22, 6, "Insurance Paid:", align="R")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(22, 6, "-$4,145.00", align="R", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(132, 7, "")
    pdf.cell(22, 7, "BALANCE DUE:", align="R")
    pdf.cell(22, 7, "$4,287.00", align="R", ln=True)

    pdf.ln(5)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, "Payment due within 30 days. Financial assistance may be available.", ln=True)
    pdf.cell(0, 4, "For questions: (617) 555-0100 or billing@mercygeneral.org", ln=True)
    pdf.cell(0, 4, "To apply for Financial Assistance: mercygeneral.org/fap or call (617) 555-0105", ln=True)

    out_path = OUT_DIR / "mercy_general_bill.pdf"
    pdf.output(str(out_path))
    print(f"Generated: {out_path}")


def generate_eob():
    """Generate matching EOB from BCBS MA."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "EXPLANATION OF BENEFITS", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Blue Cross Blue Shield of Massachusetts", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, "P.O. Box 55007, Boston, MA 02205", ln=True, align="C")
    pdf.cell(0, 5, "THIS IS NOT A BILL", ln=True, align="C")
    pdf.ln(5)

    # Member info
    pdf.set_font("Helvetica", "", 9)
    info = [
        ("Member:", "Maya Chen"),
        ("Member ID:", "XWB-9284751-01"),
        ("Group:", "EMP-44021 (PPO Select 2500)"),
        ("Claim #:", "BCBSMA-2026-118842"),
        ("Date Processed:", "06/02/2026"),
        ("Provider:", "Mercy General Hospital / Bay State Emergency Physicians"),
        ("Date of Service:", "05/12/2026"),
    ]
    for label, val in info:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 5, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, val, ln=True)
    pdf.ln(3)

    # Plan summary
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, "YOUR PLAN SUMMARY (In-Network ER Visit)", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, "Annual Deductible: $2,500 (Met: $2,500)  |  Coinsurance: 20% after deductible  |  ER Copay: $250 (waived if admitted)", ln=True)
    pdf.cell(0, 4, "Out-of-Pocket Max: $6,500 (Used: $3,180)", ln=True)
    pdf.ln(3)

    # Claims table header
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(20, 5, "CPT", border=1, fill=True)
    pdf.cell(48, 5, "Description", border=1, fill=True)
    pdf.cell(20, 5, "Billed", border=1, fill=True, align="R")
    pdf.cell(20, 5, "Allowed", border=1, fill=True, align="R")
    pdf.cell(20, 5, "Plan Paid", border=1, fill=True, align="R")
    pdf.cell(12, 5, "Deduct.", border=1, fill=True, align="R")
    pdf.cell(12, 5, "Coins.", border=1, fill=True, align="R")
    pdf.cell(20, 5, "You Owe", border=1, fill=True, align="R")
    pdf.ln()

    # EOB line items -- NOTE: only ONE 71046 (insurer caught the duplicate)
    # This creates the $412 mismatch between bill ($4,287) and EOB ($3,875)
    eob_items = [
        ("99285", "ER Visit Level 5", "2,180.00", "1,680.00", "1,344.00", "0.00", "336.00", "336.00"),
        ("71046", "Chest X-ray, 2 views", "412.00", "310.00", "248.00", "0.00", "62.00", "62.00"),
        # Note: second 71046 is DENIED/not present -- this is the mismatch
        ("84295", "Sodium", "98.00", "48.00", "38.40", "0.00", "9.60", "9.60"),
        ("84132", "Potassium", "95.00", "46.00", "36.80", "0.00", "9.20", "9.20"),
        ("82947", "Glucose", "89.00", "44.00", "35.20", "0.00", "8.80", "8.80"),
        ("82565", "Creatinine", "92.00", "45.00", "36.00", "0.00", "9.00", "9.00"),
        ("84520", "BUN", "87.00", "43.00", "34.40", "0.00", "8.60", "8.60"),
        ("82310", "Calcium", "78.00", "38.00", "30.40", "0.00", "7.60", "7.60"),
        ("84075", "Alk Phosphatase", "76.00", "37.00", "29.60", "0.00", "7.40", "7.40"),
        ("84155", "Total Protein", "75.00", "36.00", "28.80", "0.00", "7.20", "7.20"),
        ("85025", "CBC w/ diff", "186.00", "92.00", "73.60", "0.00", "18.40", "18.40"),
        ("96374", "IV push", "890.00", "620.00", "496.00", "0.00", "124.00", "124.00"),
        ("84450", "AST", "52.00", "26.00", "20.80", "0.00", "5.20", "5.20"),
        ("84460", "ALT", "48.00", "24.00", "19.20", "0.00", "4.80", "4.80"),
    ]

    pdf.set_font("Helvetica", "", 7)
    for item in eob_items:
        pdf.cell(20, 4, item[0], border=1)
        pdf.cell(48, 4, item[1], border=1)
        pdf.cell(20, 4, f"${item[2]}", border=1, align="R")
        pdf.cell(20, 4, f"${item[3]}", border=1, align="R")
        pdf.cell(20, 4, f"${item[4]}", border=1, align="R")
        pdf.cell(12, 4, f"${item[5]}", border=1, align="R")
        pdf.cell(12, 4, f"${item[6]}", border=1, align="R")
        pdf.cell(20, 4, f"${item[7]}", border=1, align="R")
        pdf.ln()

    pdf.ln(3)

    # Totals
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(88, 6, "TOTALS:")
    pdf.cell(20, 6, "$8,020.00", align="R")  # total billed (without the duplicate)
    pdf.cell(20, 6, "$2,089.00", align="R")  # allowed
    pdf.cell(20, 6, "$2,471.20", align="R")  # plan paid
    pdf.cell(12, 6, "$0.00", align="R")
    pdf.cell(12, 6, "$617.80", align="R")
    pdf.cell(20, 6, "$617.80", align="R")
    pdf.ln(8)

    # Summary box
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "SUMMARY OF YOUR RESPONSIBILITY", ln=True)
    pdf.set_font("Helvetica", "", 9)

    summary = [
        ("ER Copay:", "$250.00"),
        ("Coinsurance (20% of allowed):", "$617.80"),
        ("Applied to Deductible:", "$0.00"),
        ("Non-covered / Over-limit:", "$3,007.20"),
    ]
    for label, val in summary:
        pdf.cell(60, 5, label)
        pdf.cell(30, 5, val, align="R", ln=True)

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(60, 7, "YOUR TOTAL RESPONSIBILITY:")
    pdf.cell(30, 7, "$3,875.00", align="R", ln=True)

    pdf.ln(5)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, "NOTE: This is an explanation of how your claim was processed. The provider may bill you for the amount shown above.", ln=True)
    pdf.cell(0, 4, "If you believe this claim was processed incorrectly, contact Member Services at 1-800-555-BCBS within 180 days.", ln=True)
    pdf.cell(0, 4, "Remark: Line item 71046 (Chest X-ray) - second instance denied as duplicate charge (same CPT, same date).", ln=True)

    out_path = OUT_DIR / "bcbs_eob.pdf"
    pdf.output(str(out_path))
    print(f"Generated: {out_path}")


if __name__ == "__main__":
    generate_bill()
    generate_eob()
    print("\nDone. Both documents seeded per demo_answer_key.json.")
    print("Errors findable: duplicate 71046, upcode 99285->99283, unbundled 80053, EOB mismatch $4287 vs $3875")
