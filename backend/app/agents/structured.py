"""Structured model calls: JSON-schema response_format + Pydantic validation + one repair retry."""
from __future__ import annotations

import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.services.model_router import ChatResult, ModelRouter, TaskKind

log = logging.getLogger("paperpilot.agent")
T = TypeVar("T", bound=BaseModel)

PRIVACY_RULES = (
    "Privacy rules: personal data in the input has been replaced on the user's device by placeholders such as "
    "[NAME_1], [ADDRESS_1], [ACCOUNT_1], [EMAIL_1], [PHONE_1], [DOB_1], [ID_1]. You cannot see the real values. "
    "When an output needs one of those values, copy the placeholder exactly. Never invent personal data. "
    "You are not a lawyer: explain and draft, never give legal advice or make decisions for the user."
)


class StructuredOutputError(RuntimeError):
    pass


def _parse(text: str, model_cls: type[T]) -> T:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    return model_cls.model_validate(json.loads(text))


def structured_call(router: ModelRouter, kind: TaskKind, system: str, user: str, model_cls: type[T], *,
                    task_id: str | None, scenarios: list[str], max_output_tokens: int = 2000) -> tuple[T, list[ChatResult]]:
    schema = model_cls.model_json_schema()
    messages = [{"role": "system", "content": f"{system}\n\n{PRIVACY_RULES}\nRespond with JSON only."},
                {"role": "user", "content": user}]
    calls: list[ChatResult] = []
    res = router.chat(kind, messages, task_id=task_id, schema=schema, schema_name=model_cls.__name__,
                      scenarios=scenarios, max_output_tokens=max_output_tokens)
    calls.append(res)
    try:
        return _parse(res.text, model_cls), calls
    except (json.JSONDecodeError, ValidationError) as exc:
        error = str(exc)[:800]
        log.info("STRUCTURED_REPAIR kind=%s model=%s", kind.value, model_cls.__name__)
    repair = messages + [
        {"role": "assistant", "content": res.text[:4000]},
        {"role": "user", "content": f"That output failed validation:\n{error}\nReturn corrected JSON that matches the schema exactly."},
    ]
    res2 = router.chat(kind, repair, task_id=task_id, schema=schema, schema_name=model_cls.__name__,
                       scenarios=[f"{s}:repair" for s in scenarios], max_output_tokens=max_output_tokens)
    calls.append(res2)
    try:
        return _parse(res2.text, model_cls), calls
    except (json.JSONDecodeError, ValidationError) as exc:
        raise StructuredOutputError(f"The AI returned an invalid {model_cls.__name__} twice.") from exc
