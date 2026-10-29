import fitz

from app.config import REPO_DIR
from app.services.document_reader import read_document
from app.services.pdf_filler import OverlaySlot, PDFFormFiller, render_letter_pdf

SAMPLE = REPO_DIR / "samples" / "utility_dispute.pdf"


def test_reads_fields_with_labels_and_normalized_rects():
    doc = read_document(SAMPLE)
    names = {f.name: f for f in doc.fields}
    assert {"customer_name", "dispute_reason", "request_meter_test", "signature"} <= names.keys()
    assert names["dispute_reason"].kind == "multiline" and names["request_meter_test"].kind == "checkbox"
    assert all(0 <= v <= 1 for f in doc.fields for v in f.rect) and names["customer_name"].page == 1
    assert doc.method == "pdf-text" and "NOTICE OF HIGH BILL" in doc.text


def test_fill_acroform_and_validate():
    filler = PDFFormFiller()
    values = {"customer_name": "Amara Okafor", "disputed_amount": "612.40", "request_meter_test": "Yes",
              "request_payment_plan": "Off"}
    out = filler.fill_acroform(SAMPLE.read_bytes(), values)
    assert filler.validate_output(out, values) == []
    with fitz.open(stream=out, filetype="pdf") as d:
        stored = {w.field_name: w.field_value for w in d[1].widgets()}
    assert stored["customer_name"] == "Amara Okafor"
    assert stored["request_meter_test"] not in ("Off", "", None)
    assert filler.validate_output(out, {"customer_name": "Someone Else"}) == ["customer_name"]


def test_flat_form_overlay_writes_text_at_template_coordinates():
    blank = fitz.open()
    blank.new_page(width=612, height=792)
    out = PDFFormFiller().fill_flat_form(blank.tobytes(), {"name": OverlaySlot(0, (100, 100, 400, 130))},
                                         {"name": "Amara Okafor"})
    with fitz.open(stream=out, filetype="pdf") as d:
        words = d[0].get_text("words")
    hit = [w for w in words if w[4] == "Amara"]
    assert hit and 100 <= hit[0][0] <= 400 and 100 <= hit[0][1] <= 130


def test_final_copy_is_flattened_and_letter_renders():
    filler = PDFFormFiller()
    out = filler.flatten(filler.fill_acroform(SAMPLE.read_bytes(), {"customer_name": "Amara Okafor"}))
    with fitz.open(stream=out, filetype="pdf") as d:
        assert "Amara Okafor" in d[1].get_text()
    letter = render_letter_pdf("Billing dispute", "Dear team,\n\nI dispute this bill.\n\nAmara Okafor")
    with fitz.open(stream=letter, filetype="pdf") as d:
        assert "I dispute this bill." in d[0].get_text()
