from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import fitz

from app.api.deps import get_state
from app.db.database import now_iso
from app.services.document_reader import image_to_pdf, render_page_png
from app.state import SAMPLES, AppState

router = APIRouter(prefix="/api")
ALLOWED = {".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image"}


class FromSample(BaseModel):
    sample_id: str


def _register(state: AppState, filename: str, pdf_bytes: bytes) -> dict:
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as d:
            pages = d.page_count
    except Exception:
        raise HTTPException(400, "We couldn't open this file. Please upload a PDF or a photo.")
    doc_id = uuid.uuid4().hex[:12]
    path = state.settings.data_dir / "uploads" / f"{doc_id}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes)
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    state.db.execute("INSERT INTO documents (id, filename, path, sha256, page_count, created_at) VALUES (?,?,?,?,?,?)",
                     (doc_id, filename, str(path), sha, pages, now_iso()))
    return {"document_id": doc_id, "filename": filename, "page_count": pages,
            "original_pdf_url": f"/api/documents/{doc_id}/original.pdf"}


def document_row(state: AppState, doc_id: str) -> dict:
    rows = state.db.query("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not rows:
        raise HTTPException(404, "Document not found.")
    return rows[0]


@router.get("/samples")
def samples() -> list[dict]:
    return [{"id": k, **v} for k, v in SAMPLES.items()]


@router.post("/documents/from-sample")
def from_sample(body: FromSample, state: AppState = Depends(get_state)) -> dict:
    if body.sample_id not in SAMPLES:
        raise HTTPException(404, "Unknown sample.")
    data = (state.settings.samples_dir / f"{body.sample_id}.pdf").read_bytes()
    return _register(state, f"{body.sample_id}.pdf", data)


@router.post("/documents/upload")
async def upload(file: UploadFile = File(...), state: AppState = Depends(get_state)) -> dict:
    name = (file.filename or "document").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        raise HTTPException(400, "Please upload a PDF, PNG or JPG file.")
    data = await file.read(state.settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > state.settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {state.settings.max_upload_mb} MB.")
    if ALLOWED[ext] == "image":
        try:
            data = image_to_pdf(data)
        except Exception:
            raise HTTPException(400, "We couldn't read this image. Please upload a clearer photo.")
    safe = "".join(c for c in name if c.isalnum() or c in "._-")[:80] or "document"
    return _register(state, safe, data)


@router.get("/documents/{doc_id}/original.pdf")
def original(doc_id: str, state: AppState = Depends(get_state)):
    return FileResponse(document_row(state, doc_id)["path"], media_type="application/pdf")


@router.get("/documents/{doc_id}/pages/{n}.png")
def page_png(doc_id: str, n: int, state: AppState = Depends(get_state)):
    from pathlib import Path
    try:
        png = render_page_png(Path(document_row(state, doc_id)["path"]).read_bytes(), n)
    except IndexError:
        raise HTTPException(404, "Page not found.")
    return Response(png, media_type="image/png")
