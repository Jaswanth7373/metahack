from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_state
from app.services import deadlines as dl
from app.services.language import detect_language, lang
from app.services.model_router import BudgetExceeded, DemoCacheMiss, ModelUnavailable
from app.state import AppState

router = APIRouter(prefix="/api")


class DeadlineIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = Field(default="", max_length=1000)


@router.post("/voice/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form("auto"),
                     state: AppState = Depends(get_state)) -> dict:
    data = await audio.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024:
        raise HTTPException(413, "Recording is too long. Please keep it under 10 minutes.")
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise HTTPException(400, "Please send a WAV recording (16 kHz mono).")
    try:
        res = state.router.transcribe(data)
    except DemoCacheMiss:
        raise HTTPException(503, "Voice needs real mode (a Meta Model API key). In Demo Mode, type your request "
                                 "or use the sample's suggested request.")
    except (ModelUnavailable, BudgetExceeded) as exc:
        raise HTTPException(503, str(exc))
    detected = lang(language) if language != "auto" else detect_language(res.text)
    return {"text": res.text, "language": {"code": detected["code"], "name": detected["name"]} if detected else None,
            "model": res.model, "replayed": res.replayed, "cost_usd": res.cost_usd}


@router.get("/deadlines")
def list_deadlines(state: AppState = Depends(get_state)) -> list[dict]:
    return dl.list_deadlines(state.db)


@router.post("/deadlines")
def create_deadline(body: DeadlineIn, state: AppState = Depends(get_state)) -> dict:
    try:
        return dl.add_deadline(state.db, body.title, body.date, body.description)
    except ValueError:
        raise HTTPException(400, "Please enter a valid date.")


@router.get("/deadlines/export.ics")
def export_ics(state: AppState = Depends(get_state)):
    return Response(dl.to_ics(dl.list_deadlines(state.db)), media_type="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=paperpilot-deadlines.ics"})


@router.get("/deadlines/{deadline_id}/ics")
def one_ics(deadline_id: int, state: AppState = Depends(get_state)):
    items = [d for d in dl.list_deadlines(state.db) if d["id"] == deadline_id]
    if not items:
        raise HTTPException(404, "Deadline not found.")
    return Response(dl.to_ics(items), media_type="text/calendar",
                    headers={"Content-Disposition": f"attachment; filename=deadline-{deadline_id}.ics"})


@router.delete("/deadlines/{deadline_id}")
def remove_deadline(deadline_id: int, state: AppState = Depends(get_state)) -> dict:
    if not dl.delete_deadline(state.db, deadline_id):
        raise HTTPException(404, "Deadline not found.")
    return {"deleted": deadline_id}
