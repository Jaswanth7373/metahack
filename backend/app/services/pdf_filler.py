"""PDF form filling: AcroForm widgets, or text overlay at template coordinates for flat forms."""
from __future__ import annotations

from dataclasses import dataclass

import fitz

CHECKED = {"yes", "true", "on", "1", "x", "checked"}


@dataclass
class OverlaySlot:
    page: int
    rect: tuple[float, float, float, float]  # PDF points
    fontsize: float = 10


class PDFFormFiller:
    def fill_acroform(self, pdf_bytes: bytes, values: dict[str, str]) -> bytes:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            for w in page.widgets() or []:
                if w.field_name not in values:
                    continue
                v = values[w.field_name]
                if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                    w.field_value = w.on_state() if str(v).strip().lower() in CHECKED else "Off"
                else:
                    w.field_value = str(v)
                w.update()
        out = doc.tobytes(garbage=3, deflate=True)
        doc.close()
        return out

    def fill_flat_form(self, pdf_bytes: bytes, template: dict[str, OverlaySlot], values: dict[str, str]) -> bytes:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for name, slot in template.items():
            if values.get(name):
                doc[slot.page].insert_textbox(fitz.Rect(slot.rect), str(values[name]), fontsize=slot.fontsize,
                                              fontname="helv", color=(0.05, 0.1, 0.45))
        out = doc.tobytes(garbage=3, deflate=True)
        doc.close()
        return out

    def validate_output(self, pdf_bytes: bytes, values: dict[str, str]) -> list[str]:
        """Return names of fields whose stored value does not match what we intended to write."""
        problems: list[str] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            stored = {w.field_name: (w.field_value, w.field_type) for p in doc for w in (p.widgets() or [])}
        for name, want in values.items():
            if name not in stored:
                problems.append(name)
                continue
            got, ftype = stored[name]
            if ftype == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                if (str(want).strip().lower() in CHECKED) != (got not in (None, "", "Off", False)):
                    problems.append(name)
            elif str(got or "") != str(want):
                problems.append(name)
        return problems

    def flatten(self, pdf_bytes: bytes) -> bytes:
        """Bake field values into page content for the final, non-editable copy."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            doc.bake()
        except AttributeError:  # older PyMuPDF
            pass
        out = doc.tobytes(garbage=3, deflate=True)
        doc.close()
        return out


def render_letter_pdf(subject: str, body: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((60, 80), subject, fontsize=13, fontname="hebo")
    page.insert_textbox(fitz.Rect(60, 100, 552, 740), body, fontsize=11, fontname="helv", lineheight=1.35)
    page.insert_text((60, 770), "Drafted with PaperPilot. Review before sending - not legal advice.", fontsize=7.5,
                     fontname="helv", color=(0.45, 0.45, 0.5))
    out = doc.tobytes()
    doc.close()
    return out
