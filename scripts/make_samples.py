"""Generate the two fictional sample documents in /samples. All people, places and numbers are invented.

Each sample = page 1 notice/letter (contains the personal data) + page 2 fillable AcroForm.
Run: .venv/bin/python scripts/make_samples.py
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

OUT = Path(__file__).resolve().parent.parent / "samples"
W, H = 612, 792  # US Letter
INK = (0.12, 0.14, 0.2)
MUTED = (0.4, 0.43, 0.5)
ACCENT = (0.13, 0.32, 0.6)


def header(page: fitz.Page, org: str, sub: str) -> None:
    page.draw_rect(fitz.Rect(0, 0, W, 70), color=None, fill=ACCENT)
    page.insert_text((40, 38), org, fontsize=17, fontname="helv", color=(1, 1, 1))
    page.insert_text((40, 56), sub, fontsize=9, fontname="helv", color=(0.85, 0.9, 1))
    page.insert_text((40, H - 24), "FICTIONAL SAMPLE DOCUMENT - created for the PaperPilot demo. Not a real notice.",
                     fontsize=7.5, fontname="helv", color=MUTED)


def body(page: fitz.Page, y: float, text: str, size: float = 10.5, bold: bool = False, gap: float = 6) -> float:
    rect = fitz.Rect(40, y, W - 40, H - 40)
    font = "hebo" if bold else "helv"
    page.insert_textbox(rect, text, fontsize=size, fontname=font, color=INK, lineheight=1.25)
    lines = 0
    for para in text.split("\n"):
        lines += max(1, int(fitz.get_text_length(para, fontname=font, fontsize=size) // (W - 80)) + 1)
    return y + lines * size * 1.25 + gap


def add_text_field(page, name, label, rect, multiline=False):
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    w.field_name = name
    w.field_label = label
    w.rect = fitz.Rect(rect)
    w.text_fontsize = 0 if multiline else 10
    w.text_font = "Helv"
    w.border_color = (0.6, 0.65, 0.75)
    w.fill_color = (0.96, 0.97, 1)
    if multiline:
        w.field_flags |= fitz.PDF_TX_FIELD_IS_MULTILINE
    page.add_widget(w)


def add_checkbox(page, name, label, rect):
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    w.field_name = name
    w.field_label = label
    w.rect = fitz.Rect(rect)
    w.border_color = (0.4, 0.45, 0.55)
    page.add_widget(w)


def form_rows(page, y, rows):
    for name, label, height, kind in rows:
        page.insert_text((40, y + 11), label, fontsize=9.5, fontname="helv", color=MUTED)
        if kind == "checkbox":
            add_checkbox(page, name, label, (W - 60, y, W - 44, y + 16))
            y += 26
        else:
            add_text_field(page, name, label, (200, y, W - 40, y + height), multiline=(kind == "multiline"))
            y += height + 10
    return y


def utility_dispute() -> None:
    doc = fitz.open()
    p = doc.new_page(width=W, height=H)
    header(p, "Maplewood Valley Power & Water", "Customer Accounts Office - 900 Riverbend Plaza, Maplewood Falls, OR 97399")
    y = 92
    y = body(p, y, "NOTICE OF HIGH BILL AND RIGHT TO DISPUTE", 13, bold=True)
    y = body(p, y, "Notice date: October 20, 2026\nCustomer: Amara Okafor\nService address: 48 Willow Creek Lane, Apt 3B, "
                   "Maplewood Falls, OR 97399\nAccount number: 7731-0042-8815\nPhone on file: (541) 555-0148\n"
                   "Email on file: amara.okafor@example.com")
    y = body(p, y + 4, "Dear Ms. Okafor,")
    y = body(p, y, "Your bill for the service period September 1 - September 30, 2026 shows electricity usage of 2,940 kWh. "
                   "This is 3.1 times your 12-month average of 948 kWh. The amount due for this period is $612.40, payable by "
                   "November 3, 2026.")
    y = body(p, y, "Under Section 14.2 of the Customer Service Rules, a customer who believes a charge is incorrect may file a "
                   "billing dispute. To dispute this charge, return the enclosed Billing Dispute Response Form (page 2) no later "
                   "than November 3, 2026. While a timely dispute is under review, collection activity on the disputed amount is "
                   "suspended and no late fee will be applied to that amount. You must continue to pay any undisputed charges.")
    y = body(p, y, "You may also request a meter accuracy test at no cost, and you may ask for a payment arrangement that "
                   "spreads the balance over up to 6 months. If no dispute or payment is received by the due date, a late fee of "
                   "1.5% may be added and the account may be referred for collection after 30 days.")
    body(p, y, "Return the form by mail to the address above or by email to disputes@maplewood-pw.example.\n\n"
               "Sincerely,\nBilling Review Team, Maplewood Valley Power & Water")

    p2 = doc.new_page(width=W, height=H)
    header(p2, "Billing Dispute Response Form", "Return by November 3, 2026 - Maplewood Valley Power & Water")
    y = body(p2, 92, "Section A - Customer details", 11.5, bold=True)
    y = form_rows(p2, y, [
        ("customer_name", "Full name", 18, "text"),
        ("account_number", "Account number", 18, "text"),
        ("service_address", "Service address", 18, "text"),
        ("phone", "Phone", 18, "text"),
        ("email", "Email", 18, "text"),
    ])
    y = body(p2, y + 6, "Section B - Disputed charge", 11.5, bold=True)
    y = form_rows(p2, y, [
        ("bill_period", "Bill period disputed", 18, "text"),
        ("disputed_amount", "Amount disputed (USD)", 18, "text"),
        ("dispute_reason", "Reason for dispute", 74, "multiline"),
        ("request_meter_test", "I request a free meter accuracy test", 0, "checkbox"),
        ("request_payment_plan", "I request a payment arrangement", 0, "checkbox"),
    ])
    y = body(p2, y + 6, "Section C - Signature", 11.5, bold=True)
    form_rows(p2, y, [
        ("signature", "Signature of account holder", 22, "text"),
        ("date_signed", "Date", 18, "text"),
    ])
    doc.save(OUT / "utility_dispute.pdf", garbage=3, deflate=True)


def benefit_application() -> None:
    doc = fitz.open()
    p = doc.new_page(width=W, height=H)
    header(p, "Maplewood County Human Services", "Household Energy Assistance Program (HEAP) - 210 Civic Center Way, Maplewood Falls, OR 97399")
    y = 92
    y = body(p, y, "YOU MAY QUALIFY FOR WINTER ENERGY ASSISTANCE", 13, bold=True)
    y = body(p, y, "Letter date: October 22, 2026\nApplicant: Luis Herrera Molina\nAddress: 1207 Cedar Hollow Road, "
                   "Maplewood Falls, OR 97399\nDate of birth: 04/12/1979\nCase ID: MC-EA-55120\n"
                   "Phone: (541) 555-0193\nEmail: luis.herrera@example.com")
    y = body(p, y + 4, "Dear Mr. Herrera Molina,")
    y = body(p, y, "Our records show a household of 4 people with a reported monthly household income of $2,850. Households "
                   "at or below $3,400 per month for 4 people may receive a one-time heating credit of up to $480 for the "
                   "2026-2027 winter season.")
    y = body(p, y, "To be considered, complete the Application for Energy Assistance (page 2) and return it so that it is "
                   "received by November 20, 2026. Applications received after this date will be placed on a waiting list. "
                   "Please include the main heating source for your home. Each application must be signed and the declaration "
                   "must be completed by the applicant personally.")
    body(p, y, "If any information above is wrong, correct it on the application. Questions: call the HEAP line at "
               "(541) 555-0100, Monday to Friday, 9 am - 4 pm.\n\nMaplewood County Human Services")

    p2 = doc.new_page(width=W, height=H)
    header(p2, "Application for Energy Assistance", "Must be received by November 20, 2026 - Maplewood County HEAP")
    y = body(p2, 92, "Part 1 - Applicant", 11.5, bold=True)
    y = form_rows(p2, y, [
        ("applicant_name", "Full name", 18, "text"),
        ("date_of_birth", "Date of birth", 18, "text"),
        ("address", "Home address", 18, "text"),
        ("phone", "Phone", 18, "text"),
        ("email", "Email", 18, "text"),
        ("case_id", "Case ID (if known)", 18, "text"),
    ])
    y = body(p2, y + 6, "Part 2 - Household", 11.5, bold=True)
    y = form_rows(p2, y, [
        ("household_size", "Number of people in household", 18, "text"),
        ("monthly_income", "Total monthly household income (USD)", 18, "text"),
        ("heating_source", "Main heating source", 18, "text"),
        ("additional_info", "Anything else we should know", 56, "multiline"),
    ])
    y = body(p2, y + 6, "Part 3 - Declaration", 11.5, bold=True)
    form_rows(p2, y, [
        ("declaration", "I declare the information is true and complete", 0, "checkbox"),
        ("signature", "Signature of applicant", 22, "text"),
        ("date_signed", "Date", 18, "text"),
    ])
    doc.save(OUT / "benefit_application.pdf", garbage=3, deflate=True)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    utility_dispute()
    benefit_application()
    print("wrote", *(p.name for p in OUT.glob("*.pdf")))
