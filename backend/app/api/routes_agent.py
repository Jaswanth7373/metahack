from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from app.agents.executor import public_task
from app.api.deps import get_state
from app.api.routes_documents import document_row
from app.services.deadlines import add_deadline
from app.services.document_reader import render_page_png
from app.services.pdf_filler import PDFFormFiller, render_letter_pdf
from app.state import AppState

router = APIRouter(prefix="/api")


class RunRequest(BaseModel):
    document_id: str
    request_text: str = Field(default="", max_length=2000)
    language: str = "auto"


class FieldsPatch(BaseModel):
    values: dict[str, str]


class ConfirmRequest(BaseModel):
    confirmed: bool
    letter_body: str | None = Field(default=None, max_length=10000)


def _task(state: AppState, task_id: str) -> dict:
    task = state.store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found.")
    return task


@router.get("/health")
def health(state: AppState = Depends(get_state)) -> dict:
    s = state.settings
    return {"status": "ok", "demo_mode": s.is_demo, "privacy_engine": state.privacy.info(),
            "budget": state.router.budget(),
            "models": {"planner_verifier": s.wonder_model, "reader_writer": s.spark_model,
                       "voice": s.transcribe_model}}


@router.get("/usage")
def usage(state: AppState = Depends(get_state)) -> dict:
    calls = [{"model": r["model"], "task": r["kind"], "input_tokens": r["input_tokens"],
              "output_tokens": r["output_tokens"], "cost_usd": r["cost_usd"], "replayed": bool(r["replayed"]),
              "ts": r["ts"]} for r in state.db.recent_usage()]
    return {**state.router.budget(), "demo_mode": state.settings.is_demo, "calls": calls}


@router.post("/agent/run")
def run_agent(body: RunRequest, state: AppState = Depends(get_state)) -> dict:
    row = document_row(state, body.document_id)
    doc_key = state.sample_hashes.get(row["sha256"], row["sha256"][:12])
    task_id = state.runner.create_task(body.document_id, Path(row["path"]), doc_key, body.request_text.strip(),
                                       body.language or "auto")
    state.runner.run_async(task_id)
    return {"task_id": task_id}


@router.get("/agent/events/{task_id}")
async def events(task_id: str, state: AppState = Depends(get_state)):
    _task(state, task_id)

    async def stream():
        sent = 0
        idle = 0
        while idle < 1200:  # ~4 minutes without news -> give up
            log = state.store.events.get(task_id, [])
            if sent < len(log):
                for ev in log[sent:]:
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    if ev["type"] in ("done", "error"):
                        return
                sent = len(log)
                idle = 0
            else:
                idle += 1
                if idle % 75 == 0:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0.2)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/tasks/{task_id}")
def get_task(task_id: str, state: AppState = Depends(get_state)) -> dict:
    return public_task(_task(state, task_id))


@router.patch("/tasks/{task_id}/fields")
def patch_fields(task_id: str, body: FieldsPatch, state: AppState = Depends(get_state)) -> dict:
    task = _task(state, task_id)
    if task["status"] != "awaiting_confirmation":
        raise HTTPException(409, "This task can no longer be edited.")
    if task_id not in state.store.contexts:
        raise HTTPException(409, "This session expired. Please run the document again.")
    return public_task(state.runner.update_fields(task_id, body.values))


def _output(state: AppState, task_id: str, suffix: str) -> Path:
    p = state.settings.data_dir / "outputs" / f"{task_id}_{suffix}.pdf"
    if not p.exists():
        raise HTTPException(404, "File not ready.")
    return p


@router.get("/tasks/{task_id}/filled.pdf")
def filled_pdf(task_id: str, state: AppState = Depends(get_state)):
    return FileResponse(_output(state, task_id, "filled"), media_type="application/pdf")


@router.get("/tasks/{task_id}/filled/pages/{n}.png")
def filled_png(task_id: str, n: int, state: AppState = Depends(get_state)):
    task = _task(state, task_id)
    p = state.settings.data_dir / "outputs" / f"{task_id}_filled.pdf"
    src = p if p.exists() else Path(document_row(state, task["document_id"])["path"])
    try:
        return Response(render_page_png(src.read_bytes(), n), media_type="image/png",
                        headers={"Cache-Control": "no-store"})
    except IndexError:
        raise HTTPException(404, "Page not found.")


@router.get("/tasks/{task_id}/final.pdf")
def final_pdf(task_id: str, state: AppState = Depends(get_state)):
    return FileResponse(_output(state, task_id, "final"), media_type="application/pdf",
                        filename="paperpilot-completed-form.pdf")


@router.get("/tasks/{task_id}/letter.pdf")
def letter_pdf(task_id: str, state: AppState = Depends(get_state)):
    return FileResponse(_output(state, task_id, "letter"), media_type="application/pdf",
                        filename="paperpilot-response-letter.pdf")


@router.post("/tasks/{task_id}/confirm")
def confirm(task_id: str, body: ConfirmRequest, state: AppState = Depends(get_state)) -> dict:
    """The only place outputs are finalized, and only with an explicit confirmed=true from the user."""
    task = _task(state, task_id)
    if not body.confirmed:
        raise HTTPException(400, "Nothing was finalized: confirmation is required.")
    if task["status"] != "awaiting_confirmation":
        raise HTTPException(409, "This task is not waiting for confirmation.")
    out_dir = state.settings.data_dir / "outputs"
    filler = PDFFormFiller()
    filled = out_dir / f"{task_id}_filled.pdf"
    if filled.exists():
        (out_dir / f"{task_id}_final.pdf").write_bytes(filler.flatten(filled.read_bytes()))
        task["final_pdf_url"] = f"/api/tasks/{task_id}/final.pdf"
    if task.get("letter"):
        if body.letter_body:
            task["letter"]["body"] = body.letter_body
        (out_dir / f"{task_id}_letter.pdf").write_bytes(render_letter_pdf(task["letter"]["subject"], task["letter"]["body"]))
        task["letter_pdf_url"] = f"/api/tasks/{task_id}/letter.pdf"
    task["deadlines"] = [add_deadline(state.db, d["title"], d["date"], d.get("description", ""), task_id)
                         for d in task.get("deadlines", [])]
    task["status"] = "confirmed"
    for s in task["steps"]:
        if s["tool"] == "ask_user_confirmation":
            s["status"], s["detail"] = "done", "Confirmed by you"
    state.store.save(task)
    return public_task(task)


@router.get("/privacy/{task_id}")
def privacy(task_id: str, state: AppState = Depends(get_state)) -> dict:
    _task(state, task_id)
    vault = state.store.vaults.get(task_id)
    ctx = state.store.contexts.get(task_id)
    if not vault or not ctx:
        raise HTTPException(409, "Privacy details are only kept in memory for this session.")
    from app.services.privacy import TYPE_LABELS
    rows = state.db.query("SELECT model, kind, chars, raw_pii_found FROM privacy_events WHERE task_id=? ORDER BY id",
                          (task_id,))
    return {
        "engine": state.privacy.info(),
        "items": [{"placeholder": i.placeholder, "type": i.type, "type_label": TYPE_LABELS.get(i.type, i.type),
                   "original": i.original} for i in vault.items.values()],
        "original_excerpt": ctx.doc.text[:1600],
        "sanitized_excerpt": ctx.redacted_text[:1600],
        "cloud_requests": [{"model": r["model"], "task": r["kind"], "replayed": state.settings.is_demo,
                            "chars": r["chars"], "raw_pii_found": r["raw_pii_found"]} for r in rows],
        "raw_pii_sent": sum(r["raw_pii_found"] for r in rows),
        "protected_count": len(vault.items),
    }
