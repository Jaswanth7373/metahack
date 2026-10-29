"""PaperPilot API. Run: uvicorn app.main:app --reload (from backend/)."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import routes_agent, routes_documents, routes_misc
from app.config import REPO_DIR, Settings, get_settings
from app.services.model_router import Transport
from app.state import build_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings: Settings | None = None, transport: Transport | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="PaperPilot", version="0.1.0")
    app.state.pp = build_state(settings, transport=transport)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    for r in (routes_documents.router, routes_agent.router, routes_misc.router):
        app.include_router(r)

    @app.exception_handler(Exception)
    async def friendly_errors(request: Request, exc: Exception):  # never show stack traces to users
        logging.getLogger("paperpilot").exception("UNHANDLED %s", request.url.path)
        return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)

    dist = REPO_DIR / "frontend" / "dist"
    if dist.exists():  # single-process demo: serve the built UI too
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = dist / path
            return FileResponse(f if path and f.is_file() else dist / "index.html")

    return app


app = create_app()
