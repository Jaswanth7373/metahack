"""Agent tools. Cloud tools only ever receive redacted text; restore() runs locally afterwards."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from app.agents.schemas import Deadlines, Explanation, FillResult, Letter
from app.agents.structured import structured_call
from app.services.document_reader import ReadResult
from app.services.model_router import ChatResult, ModelRouter, TaskKind
from app.services.privacy import Vault

USER_ONLY = re.compile(r"signature|declar|attest|consent", re.I)
PLACEHOLDER = re.compile(r"\[[A-Z]+_\d+\]")
REVIEW_THRESHOLD = 0.8


@dataclass
class TaskContext:
    task_id: str
    task: dict
    vault: Vault
    doc: ReadResult
    pdf_bytes: bytes
    redacted_text: str
    redacted_request: str
    doc_key: str
    lang: dict
    intent: str = ""
    raw_fills: dict[str, dict] = field(default_factory=dict)  # name -> {value (placeholders), confidence, note}

    def scen(self, kind: str, per_language: bool = False) -> list[str]:
        if per_language:
            return [f"{kind}:{self.doc_key}:{self.lang['code']}", f"{kind}:{self.doc_key}:en"]
        return [f"{kind}:{self.doc_key}"]


@dataclass
class ToolOutcome:
    detail: str
    calls: list[ChatResult] = field(default_factory=list)


def _in_language(ctx: TaskContext) -> str:
    return f"Write all text for the user in {ctx.lang['english_name']} (language code {ctx.lang['code']}), simply, at a 6th-grade reading level."


def explain_document(router: ModelRouter, ctx: TaskContext) -> ToolOutcome:
    system = ("You explain official paperwork in plain language. Say what the document is, what it means for the "
              "person, and the concrete next steps, including any amounts and dates. " + _in_language(ctx))
    user = f"User request: {ctx.redacted_request}\n\nDocument:\n{ctx.redacted_text}"
    out, calls = structured_call(router, TaskKind.EXPLAIN, system, user, Explanation, task_id=ctx.task_id,
                                 scenarios=ctx.scen("explain", True))
    ctx.task["explanation"] = {k: _restore(ctx, v) for k, v in out.model_dump().items()}
    return ToolOutcome(f"{len(out.steps)} next steps in {ctx.lang['name']}", calls)


def extract_deadline(router: ModelRouter, ctx: TaskContext) -> ToolOutcome:
    system = (f"Extract important deadlines from the document. Today is {date.today().isoformat()}. Use ISO dates "
              "(YYYY-MM-DD). Titles are short reminders. " + _in_language(ctx))
    out, calls = structured_call(router, TaskKind.EXTRACT_DEADLINES, system, ctx.redacted_text, Deadlines,
                                 task_id=ctx.task_id, scenarios=ctx.scen("deadlines", True), max_output_tokens=600)
    ctx.task["deadlines"] = [_with_days(d.model_dump()) for d in out.deadlines]
    first = ctx.task["deadlines"][0]["date"] if ctx.task["deadlines"] else "none found"
    return ToolOutcome(f"Next deadline: {first}", calls)


def fill_form(router: ModelRouter, ctx: TaskContext) -> ToolOutcome:
    fillable = [f for f in ctx.doc.fields if not USER_ONLY.search(f.name + " " + f.label)]
    spec = [{"name": f.name, "label": f.label, "kind": f.kind} for f in fillable]
    system = ("Fill the form fields using only facts from the document and the user's request. For checkboxes use "
              "\"Yes\" or \"Off\". Write field text in the form's language (the document's language). If a value is "
              "unknown leave it empty with low confidence. Use today's date "
              f"({date.today().strftime('%B %d, %Y')}) for date-signed fields with confidence 0.6. Never sign for the user.")
    user = (f"User request: {ctx.redacted_request}\n\nForm fields:\n{json.dumps(spec, ensure_ascii=False)}\n\n"
            f"Document:\n{ctx.redacted_text}")
    out, calls = structured_call(router, TaskKind.FILL, system, user, FillResult, task_id=ctx.task_id,
                                 scenarios=ctx.scen("fill"))
    allowed = {f.name for f in fillable}
    ctx.raw_fills = {fv.name: fv.model_dump() for fv in out.fields if fv.name in allowed}
    _sync_fields(ctx)
    return ToolOutcome(f"{sum(1 for v in ctx.raw_fills.values() if v['value'])} of {len(ctx.doc.fields)} fields filled", calls)


def draft_response(router: ModelRouter, ctx: TaskContext) -> ToolOutcome:
    system = ("Draft a short, polite, factual reply letter from the user to the sender of this document, doing what the "
              "user asked. Write the letter in the document's language so the recipient can read it. Include the "
              "account/case reference placeholders and sign with the user's name placeholder. No legal threats.")
    user = f"User request: {ctx.redacted_request}\n\nDocument:\n{ctx.redacted_text}"
    out, calls = structured_call(router, TaskKind.DRAFT, system, user, Letter, task_id=ctx.task_id,
                                 scenarios=ctx.scen("draft"))
    ctx.task["letter"] = {"subject": _restore(ctx, out.subject), "body": _restore(ctx, out.body)}
    return ToolOutcome(f"Letter drafted: {len(out.body.split())} words", calls)


def add_deadline(router: ModelRouter, ctx: TaskContext) -> ToolOutcome:
    n = len(ctx.task.get("deadlines", []))
    return ToolOutcome(f"{n} reminder(s) staged - saved when you confirm")


def _restore(ctx: TaskContext, value):
    if isinstance(value, list):
        return [ctx.vault.restore(v) for v in value]
    return ctx.vault.restore(value) if isinstance(value, str) else value


def _with_days(d: dict) -> dict:
    try:
        d["days_remaining"] = (date.fromisoformat(d["date"]) - date.today()).days
    except ValueError:
        d["days_remaining"] = None
    return d


def _sync_fields(ctx: TaskContext, checks: dict[str, dict] | None = None) -> None:
    """Build the UI field list: values restored locally, review flags from confidence + verifier + safety rules."""
    checks = checks or {}
    fields = []
    for f in ctx.doc.fields:
        raw = ctx.raw_fills.get(f.name, {"value": "", "confidence": 0.0, "note": None})
        chk = checks.get(f.name, {})
        conf = min(raw["confidence"], chk.get("confidence", 1.0))
        note = chk.get("note") or raw.get("note")
        user_only = bool(USER_ONLY.search(f.name + " " + f.label))
        if user_only:
            note = "Only you can sign or make this declaration. PaperPilot leaves it for you."
        value = ctx.vault.restore(raw["value"] or "")
        if f.kind == "checkbox":
            value = "Yes" if value.strip().lower() in {"yes", "true", "on", "1", "x"} else "Off"
        fields.append({
            "name": f.name, "label": f.label, "value": value, "confidence": round(conf, 2),
            "needs_review": user_only or conf < REVIEW_THRESHOLD or bool(chk.get("needs_review")),
            "note": note, "kind": f.kind, "contains_pii": bool(PLACEHOLDER.search(raw["value"] or "")),
            "page": f.page, "rect": list(f.rect),
        })
    ctx.task["fields"] = fields


TOOLS = {
    "explain_document": (explain_document, "Explaining in plain language", "spark"),
    "extract_deadline": (extract_deadline, "Finding important dates", "spark"),
    "fill_form": (fill_form, "Filling the form", "spark"),
    "draft_response": (draft_response, "Drafting a response letter", "spark"),
    "add_deadline": (add_deadline, "Preparing deadline reminders", None),
}
