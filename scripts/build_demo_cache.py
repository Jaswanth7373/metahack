"""Write the DEMO_MODE response cache for the two sample documents.

These are hand-written stand-ins for model responses, written against the *redacted* sample text (so they
only contain placeholders), with estimated token counts. Each entry says so in its "source" field.
Once a MODEL_API_KEY is set, replace them with real recorded responses:

    DEMO_MODE=false RECORD_DEMO_CACHE=true  -> run both samples once in the app

Run: .venv/bin/python scripts/build_demo_cache.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "backend" / "demo_cache" / "scenario"
SOURCE = "hand-authored demo fixture (estimated token counts); re-record in real mode to replace"
SPARK, WONDER = "muse-spark-1.3", "muse-wonder-1.0"


def put(key: str, model: str, content: dict, prompt_tokens: int, completion_tokens: int) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    entry = {"kind": key.split(":")[0], "model": model, "source": SOURCE,
             "content": json.dumps(content, ensure_ascii=False),
             "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}}
    (ROOT / f"{key.replace(':', '_')}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- utility dispute (Hindi request)
U = "utility_dispute"
put(f"plan:{U}", WONDER, {
    "document_type": "utility_high_bill_dispute_notice",
    "document_title": "Notice of High Bill and Right to Dispute",
    "intent": "Dispute the September 2026 electricity charge and request a meter test before the deadline",
    "actions": [
        {"tool": "explain_document", "reason": "The user says they do not understand the notice; explain it in Hindi."},
        {"tool": "extract_deadline", "reason": "The dispute form must be returned by a fixed date."},
        {"tool": "fill_form", "reason": "Page 2 is a Billing Dispute Response Form the user wants to submit."},
        {"tool": "draft_response", "reason": "A short cover letter makes the dispute and meter-test request explicit."},
        {"tool": "verify_form", "reason": "Check every filled value against the notice before the user reviews it."},
        {"tool": "add_deadline", "reason": "Save the response deadline as a reminder."},
        {"tool": "ask_user_confirmation", "reason": "The user must review and confirm before anything is final."},
    ],
}, 2650, 420)

EXPLAIN_U_HI = {
    "summary": "यह बिजली कंपनी का नोटिस है। सितंबर 2026 का आपका बिल $612.40 है, जो आपके सामान्य इस्तेमाल से लगभग 3 गुना ज़्यादा है।",
    "what_it_means": "कंपनी के अनुसार सितंबर में 2,940 kWh बिजली इस्तेमाल हुई, जबकि आपका 12 महीने का औसत 948 kWh है। "
                     "अगर आपको लगता है कि बिल गलत है, तो आप 3 नवंबर 2026 तक विवाद (dispute) फ़ॉर्म भेज सकते हैं। "
                     "जांच के दौरान विवादित रकम पर वसूली रुकी रहेगी और उस पर लेट फीस नहीं लगेगी।",
    "steps": [
        "पेज 2 का 'Billing Dispute Response Form' जांचें — PaperPilot ने इसे आपके लिए भर दिया है।",
        "मुफ़्त मीटर जांच (meter accuracy test) का विकल्प चुना गया है — पुष्टि करें कि आप यही चाहते हैं।",
        "फ़ॉर्म पर खुद हस्ताक्षर करें और तारीख़ लिखें।",
        "3 नवंबर 2026 से पहले फ़ॉर्म डाक से या [EMAIL_1] पर ईमेल से भेजें।",
        "जो रकम विवाद में नहीं है, उसका भुगतान समय पर करते रहें।",
    ],
    "warnings": [
        "अगर 3 नवंबर तक न विवाद भेजा गया और न भुगतान हुआ, तो 1.5% लेट फीस लग सकती है और 30 दिन बाद खाता वसूली में जा सकता है।",
        "PaperPilot कानूनी सलाह नहीं देता — अंतिम फ़ैसला आपका है।",
    ],
}
EXPLAIN_U_EN = {
    "summary": "This is a notice from your power company. Your September 2026 bill is $612.40, about 3 times your normal usage.",
    "what_it_means": "The company says you used 2,940 kWh in September, while your 12-month average is 948 kWh. If you think "
                     "the bill is wrong, you can dispute it by returning the form by November 3, 2026. While the dispute is "
                     "reviewed, they will not collect the disputed amount or add a late fee to it.",
    "steps": [
        "Check the Billing Dispute Response Form on page 2 — PaperPilot has filled it in for you.",
        "A free meter accuracy test is selected — confirm that is what you want.",
        "Sign and date the form yourself.",
        "Send it by mail or email it to [EMAIL_1] before November 3, 2026.",
        "Keep paying any charges you are not disputing.",
    ],
    "warnings": [
        "If nothing is received by November 3, a 1.5% late fee may be added and the account may go to collection after 30 days.",
        "PaperPilot does not give legal advice — the final decision is yours.",
    ],
}
put(f"explain:{U}:hi", SPARK, EXPLAIN_U_HI, 2300, 700)
put(f"explain:{U}:en", SPARK, EXPLAIN_U_EN, 2300, 520)
put(f"deadlines:{U}:hi", SPARK, {"deadlines": [
    {"title": "बिजली बिल विवाद फ़ॉर्म भेजें", "date": "2026-11-03",
     "description": "Billing Dispute Response Form Maplewood Valley Power & Water तक पहुँचना चाहिए।"}]}, 1900, 120)
put(f"deadlines:{U}:en", SPARK, {"deadlines": [
    {"title": "Send utility bill dispute form", "date": "2026-11-03",
     "description": "The Billing Dispute Response Form must reach Maplewood Valley Power & Water."}]}, 1900, 110)
put(f"fill:{U}", SPARK, {"fields": [
    {"name": "customer_name", "value": "[NAME_1]", "confidence": 0.99, "note": None},
    {"name": "account_number", "value": "[ACCOUNT_1]", "confidence": 0.99, "note": None},
    {"name": "service_address", "value": "[ADDRESS_1]", "confidence": 0.98, "note": None},
    {"name": "phone", "value": "[PHONE_1]", "confidence": 0.95, "note": "Phone on file in the notice"},
    {"name": "email", "value": "[EMAIL_2]", "confidence": 0.95, "note": "Email on file in the notice"},
    {"name": "bill_period", "value": "September 1 - September 30, 2026", "confidence": 0.97, "note": None},
    {"name": "disputed_amount", "value": "612.40", "confidence": 0.9, "note": "Full bill amount; reduce it if only part is disputed"},
    {"name": "dispute_reason", "value": "The bill shows 2,940 kWh for September 2026, about 3.1 times my 12-month average "
                                         "of 948 kWh. This is far above my normal usage and I believe the meter reading or "
                                         "the charge may be incorrect. I request a review and a meter accuracy test.",
     "confidence": 0.8, "note": "Written from the bill comparison and your request"},
    {"name": "request_meter_test", "value": "Yes", "confidence": 0.92, "note": "You asked for a meter check"},
    {"name": "request_payment_plan", "value": "Off", "confidence": 0.85, "note": "You did not ask for a payment plan"},
    {"name": "date_signed", "value": "", "confidence": 0.0, "note": "Write the date when you sign"},
]}, 2750, 560)
put(f"draft:{U}", SPARK, {
    "subject": "Billing dispute - account [ACCOUNT_1], September 2026 bill",
    "body": "Dear Billing Review Team,\n\nI am writing to dispute the charge of $612.40 on my bill for the service period "
            "September 1 - September 30, 2026 (account [ACCOUNT_1], service address [ADDRESS_1]).\n\nThe bill shows usage "
            "of 2,940 kWh, about 3.1 times my 12-month average of 948 kWh. This is far above my normal usage, and I believe "
            "the meter reading or the charge may be incorrect.\n\nUnder Section 14.2 of your Customer Service Rules, I ask "
            "that you:\n1. review this charge as a billing dispute, with collection on the disputed amount suspended and no "
            "late fee applied while it is under review; and\n2. carry out a free meter accuracy test.\n\nI will continue to "
            "pay any undisputed charges. Please contact me at [PHONE_1] or [EMAIL_2] with the result of the review.\n\n"
            "Sincerely,\n[NAME_1]",
}, 2350, 330)
put(f"verify:{U}", WONDER, {
    "overall_confidence": 0.86,
    "summary": "Name, account, address and contact details match the notice exactly. The dispute reason is supported by the "
               "bill figures but should be confirmed in the account holder's own words.",
    "issues": ["Reason for dispute: confirm it describes your situation (for example, if you were away or nothing changed at home).",
               "Signature and date must be added by the account holder."],
    "fields": [
        {"name": "customer_name", "confidence": 0.99, "needs_review": False, "note": None},
        {"name": "account_number", "confidence": 0.99, "needs_review": False, "note": None},
        {"name": "service_address", "confidence": 0.98, "needs_review": False, "note": None},
        {"name": "bill_period", "confidence": 0.97, "needs_review": False, "note": None},
        {"name": "disputed_amount", "confidence": 0.88, "needs_review": False, "note": None},
        {"name": "dispute_reason", "confidence": 0.76, "needs_review": True,
         "note": "Inferred from the bill comparison. Add details only you know."},
        {"name": "request_meter_test", "confidence": 0.93, "needs_review": False, "note": None},
    ],
}, 3300, 480)

# --------------------------------------------------------------------------- benefit application (Spanish request)
B = "benefit_application"
put(f"plan:{B}", WONDER, {
    "document_type": "energy_assistance_application",
    "document_title": "Household Energy Assistance Program - Application",
    "intent": "Apply for the winter energy assistance credit before the deadline",
    "actions": [
        {"tool": "explain_document", "reason": "Explain the eligibility letter and what the credit is, in Spanish."},
        {"tool": "extract_deadline", "reason": "The application must be received by a fixed date."},
        {"tool": "fill_form", "reason": "Page 2 is the application; most answers are in the letter and the user's request."},
        {"tool": "verify_form", "reason": "Income and household facts must match the letter and what the user said."},
        {"tool": "add_deadline", "reason": "Save the application deadline as a reminder."},
        {"tool": "ask_user_confirmation", "reason": "The applicant must review, sign and make the declaration personally."},
    ],
}, 2550, 380)
put(f"explain:{B}:es", SPARK, {
    "summary": "Es una carta del condado de Maplewood: su hogar podría recibir un crédito único de hasta $480 para la calefacción este invierno.",
    "what_it_means": "Según sus registros, en su casa viven 4 personas con ingresos de $2,850 al mes. Los hogares de 4 personas "
                     "con ingresos de hasta $3,400 al mes pueden recibir la ayuda. Para pedirla, la solicitud (página 2) debe "
                     "llegar antes del 20 de noviembre de 2026.",
    "steps": [
        "Revise la solicitud de la página 2 — PaperPilot ya la llenó con los datos de la carta y lo que usted dijo.",
        "Confirme que sus ingresos mensuales siguen siendo $2,850; si cambiaron, corríjalos.",
        "Marque usted mismo la declaración y firme la solicitud.",
        "Envíela para que llegue antes del 20 de noviembre de 2026.",
    ],
    "warnings": [
        "Si llega después del 20 de noviembre, la solicitud queda en lista de espera.",
        "PaperPilot no da asesoría legal — usted decide y confirma todo.",
    ],
}, 2200, 520)
put(f"explain:{B}:en", SPARK, {
    "summary": "This is a letter from Maplewood County: your household may get a one-time heating credit of up to $480 this winter.",
    "what_it_means": "Their records show 4 people in your home with $2,850 monthly income. Households of 4 earning up to $3,400 "
                     "a month can qualify. To apply, the application on page 2 must be received by November 20, 2026.",
    "steps": [
        "Check the application on page 2 — PaperPilot filled it from the letter and your request.",
        "Confirm your monthly income is still $2,850; correct it if it changed.",
        "Tick the declaration and sign the application yourself.",
        "Send it so it arrives before November 20, 2026.",
    ],
    "warnings": ["Applications received after November 20 go on a waiting list.",
                 "PaperPilot does not give legal advice — you decide and confirm everything."],
}, 2200, 430)
put(f"deadlines:{B}:es", SPARK, {"deadlines": [
    {"title": "Enviar solicitud de ayuda de energía", "date": "2026-11-20",
     "description": "La solicitud debe llegar a Maplewood County Human Services."}]}, 1800, 100)
put(f"deadlines:{B}:en", SPARK, {"deadlines": [
    {"title": "Send energy assistance application", "date": "2026-11-20",
     "description": "The application must be received by Maplewood County Human Services."}]}, 1800, 95)
put(f"fill:{B}", SPARK, {"fields": [
    {"name": "applicant_name", "value": "[NAME_1]", "confidence": 0.99, "note": None},
    {"name": "date_of_birth", "value": "[DOB_1]", "confidence": 0.98, "note": None},
    {"name": "address", "value": "[ADDRESS_1]", "confidence": 0.98, "note": None},
    {"name": "phone", "value": "[PHONE_1]", "confidence": 0.96, "note": None},
    {"name": "email", "value": "[EMAIL_1]", "confidence": 0.96, "note": None},
    {"name": "case_id", "value": "[ID_1]", "confidence": 0.99, "note": None},
    {"name": "household_size", "value": "4", "confidence": 0.97, "note": "Letter and your request both say 4"},
    {"name": "monthly_income", "value": "2,850", "confidence": 0.8, "note": "From the county's records in the letter"},
    {"name": "heating_source", "value": "Electricity", "confidence": 0.9, "note": "From your spoken request"},
    {"name": "additional_info", "value": "", "confidence": 0.9, "note": "Optional"},
    {"name": "date_signed", "value": "", "confidence": 0.0, "note": "Write the date when you sign"},
]}, 2650, 420)
put(f"verify:{B}", WONDER, {
    "overall_confidence": 0.84,
    "summary": "Identity and contact fields match the letter. Household size and heating source match the applicant's request. "
               "Income is copied from county records and may be out of date.",
    "issues": ["Monthly income comes from the county's records - check it is still correct.",
               "The declaration and signature must be completed by the applicant personally."],
    "fields": [
        {"name": "applicant_name", "confidence": 0.99, "needs_review": False, "note": None},
        {"name": "case_id", "confidence": 0.99, "needs_review": False, "note": None},
        {"name": "household_size", "confidence": 0.96, "needs_review": False, "note": None},
        {"name": "monthly_income", "confidence": 0.74, "needs_review": True,
         "note": "Copied from county records; update it if your income changed."},
        {"name": "heating_source", "confidence": 0.9, "needs_review": False, "note": None},
    ],
}, 3100, 420)

if __name__ == "__main__":
    print("wrote", len(list(ROOT.glob("*.json"))), "scenario files to", ROOT)
