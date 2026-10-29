"""Local-first document reading: PDF text layer via PyMuPDF, Tesseract OCR for photos/scans.

Nothing here touches the network. Raw images are never sent to a cloud model; only the
locally redacted text is (see privacy.py).
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

import fitz

log = logging.getLogger("paperpilot.reader")


class UnreadableDocument(RuntimeError):
    pass


@dataclass
class FormField:
    name: str
    label: str
    kind: str  # text | multiline | checkbox
    page: int
    rect: tuple[float, float, float, float]  # normalized 0..1


@dataclass
class ReadResult:
    text: str
    page_count: int
    method: str  # "pdf-text" | "tesseract-ocr"
    fields: list[FormField] = field(default_factory=list)


def image_to_pdf(data: bytes) -> bytes:
    """Wrap a photo in a one-page PDF so every document has the same shape downstream."""
    img = fitz.open(stream=data, filetype=_image_type(data))
    pdf_bytes = img.convert_to_pdf()
    return pdf_bytes


def _image_type(data: bytes) -> str:
    return "png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "jpeg"


def _ocr_page(page: fitz.Page) -> str:
    import pytesseract
    from PIL import Image

    pix = page.get_pixmap(dpi=300)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img)


def extract_fields(doc: fitz.Document) -> list[FormField]:
    fields: list[FormField] = []
    for pno, page in enumerate(doc):
        pw, ph = page.rect.width, page.rect.height
        for w in page.widgets() or []:
            if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                kind = "checkbox"
            elif w.field_type == fitz.PDF_WIDGET_TYPE_TEXT:
                kind = "multiline" if w.field_flags & fitz.PDF_TX_FIELD_IS_MULTILINE else "text"
            else:
                continue
            r = w.rect
            fields.append(FormField(w.field_name, w.field_label or w.field_name.replace("_", " ").title(), kind, pno,
                                    (r.x0 / pw, r.y0 / ph, r.x1 / pw, r.y1 / ph)))
    return fields


def read_document(path: Path) -> ReadResult:
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise UnreadableDocument("We couldn't open this file. Please upload a PDF or a photo.") from exc
    with doc:
        texts = [p.get_text().strip() for p in doc]
        method = "pdf-text"
        if sum(len(t) for t in texts) < 40:  # scanned PDF or photo: OCR locally
            try:
                texts = [_ocr_page(p).strip() for p in doc]
            except Exception as exc:
                raise UnreadableDocument("We couldn't read this document clearly. Please upload a clearer image.") from exc
            method = "tesseract-ocr"
        text = "\n\n".join(f"--- Page {i + 1} ---\n{t}" for i, t in enumerate(texts))
        if len(text.strip()) < 40:
            raise UnreadableDocument("We couldn't read this document clearly. Please upload a clearer image.")
        return ReadResult(text=text, page_count=doc.page_count, method=method, fields=extract_fields(doc))


def render_page_png(pdf_bytes: bytes, page: int, zoom: float = 1.6) -> bytes:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if not 0 <= page < doc.page_count:
            raise IndexError("page out of range")
        return doc[page].get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png")
