"""Planner (Muse Wonder): decides which tools to run for this document and request."""
from __future__ import annotations

from app.agents.schemas import Plan
from app.agents.structured import structured_call
from app.services.model_router import ModelRouter, TaskKind

SYSTEM = """You are the planner of PaperPilot, an agent that helps people handle official paperwork.
Decide which tools to run, in order, to do what the user asked with this document.
Available tools:
- explain_document: plain-language explanation and next steps in the user's language
- extract_deadline: find important dates (response due dates, payment dates)
- fill_form: fill the fillable form fields from the document and the user's request
- draft_response: draft a reply letter to the sender, if a written response helps the user
- add_deadline: save the extracted deadlines as reminders (requires extract_deadline first)
- verify_form: check every filled value against the document (required after fill_form)
- ask_user_confirmation: pause for the user to review and confirm (always last)
Only plan fill_form if the document has form fields. Give a short reason for every action."""


def make_plan(router: ModelRouter, *, task_id: str, redacted_text: str, redacted_request: str,
              fields_summary: str, language_name: str, doc_key: str):
    user = (f"User request (spoken in {language_name}): {redacted_request or '(none - help me with this document)'}\n\n"
            f"Fillable form fields: {fields_summary or 'none'}\n\nDocument text:\n{redacted_text}")
    return structured_call(router, TaskKind.PLAN, SYSTEM, user, Plan, task_id=task_id,
                           scenarios=[f"plan:{doc_key}"], max_output_tokens=1200)


def enforce_plan_invariants(plan: Plan, has_fields: bool, max_steps: int) -> list[str]:
    """Safety rules live in code, not in the prompt: explanation first, verification after filling,
    deadlines extracted before saving, confirmation always last, bounded length."""
    tools = [a.tool for a in plan.actions]
    will_fill = has_fields and "fill_form" in tools
    ordered: list[str] = []
    for t in ["explain_document"] + tools:
        if t == "ask_user_confirmation" or t in ordered:
            continue
        if t in ("fill_form", "verify_form") and not will_fill:
            continue
        if t == "add_deadline" and "extract_deadline" not in ordered:
            ordered.append("extract_deadline")
        ordered.append(t)
    if "fill_form" in ordered and "verify_form" not in ordered:
        ordered.append("verify_form")
    if "verify_form" in ordered:  # verification must see the final filled values
        ordered.remove("verify_form")
        ordered.append("verify_form")
    return ordered[: max_steps - 1] + ["ask_user_confirmation"]
