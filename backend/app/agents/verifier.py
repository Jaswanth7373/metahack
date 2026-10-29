"""Verifier (Muse Wonder) + deterministic local checks on the filled form."""
from __future__ import annotations

import json

from app.agents.schemas import Verification
from app.agents.structured import structured_call
from app.services.model_router import ModelRouter, TaskKind

SYSTEM = """You are the verifier of PaperPilot. Check each filled form value against the document text and the
user's request. Flag a field (needs_review=true) when the value is unsupported by the document or request,
inferred rather than stated, or a judgment the user must make. Placeholders like [NAME_1] are correct when
the document shows that placeholder for that item. Give confidence 0..1 per field and overall."""


def verify(router: ModelRouter, *, task_id: str, redacted_text: str, redacted_request: str,
           filled: list[dict], intent: str, doc_key: str):
    user = (f"Plan intent: {intent}\nUser request: {redacted_request}\n\nFilled values (JSON):\n"
            f"{json.dumps(filled, ensure_ascii=False)}\n\nDocument text:\n{redacted_text}")
    return structured_call(router, TaskKind.VERIFY, SYSTEM, user, Verification, task_id=task_id,
                           scenarios=[f"verify:{doc_key}"], max_output_tokens=1500)
