"""Agent executor: read -> redact -> plan -> tools -> verify -> pause for the user's confirmation.

Every step is streamed as an event (model used, local vs cloud, cost). Bounded by MAX_AGENT_STEPS and a
per-task cost cap. Nothing is finalized here: the run always ends waiting for explicit confirmation.
"""
from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict
from pathlib import Path

from app.agents.planner import enforce_plan_invariants, make_plan
from app.agents.structured import StructuredOutputError
from app.agents.verifier import verify
from app.db.database import Database
from app.services.document_reader import UnreadableDocument, read_document
from app.services.language import detect_language, lang
from app.services.model_router import BudgetExceeded, DemoCacheMiss, ModelRouter, ModelUnavailable, PrivacyViolation
from app.services.pdf_filler import PDFFormFiller
from app.services.privacy import PrivacyEngine, Vault
from app.tools.registry import TOOLS, TaskContext, _sync_fields

log = logging.getLogger("paperpilot.executor")


class TaskStore:
    """In-memory task state + event log (persisted to SQLite). Vaults never leave this process."""

    def __init__(self, db: Database):
        self.db = db
        self.tasks: dict[str, dict] = {}
        self.events: dict[str, list[dict]] = defaultdict(list)
        self.vaults: dict[str, Vault] = {}
        self.contexts: dict[str, TaskContext] = {}
        self.cond = threading.Condition()

    def emit(self, task_id: str, event: dict) -> None:
        with self.cond:
            self.events[task_id].append(event)
            self.cond.notify_all()

    def save(self, task: dict) -> None:
        self.tasks[task["task_id"]] = task
        self.db.save_task(task["task_id"], task["document_id"], task["status"], task)

    def get(self, task_id: str) -> dict | None:
        return self.tasks.get(task_id) or self.db.load_task(task_id)

    def guard(self, task_id: str | None, payload: str) -> int:
        """Router guard: count raw values from this task's vault that appear in an outgoing payload."""
        vault = self.vaults.get(task_id or "")
        return vault.leaked_values(payload) if vault else 0


class AgentRunner:
    def __init__(self, router: ModelRouter, privacy: PrivacyEngine, store: TaskStore, *, outputs_dir: Path,
                 max_steps: int, task_cost_cap: float):
        self.router = router
        self.privacy = privacy
        self.store = store
        self.outputs = outputs_dir
        self.max_steps = max_steps
        self.task_cost_cap = task_cost_cap
        self.filler = PDFFormFiller()
        router.add_guard(store.guard)

    # ---------------------------------------------------------------- lifecycle
    def create_task(self, document_id: str, pdf_path: Path, doc_key: str, request_text: str, language: str) -> str:
        task_id = uuid.uuid4().hex[:12]
        task = {
            "task_id": task_id, "document_id": document_id, "status": "running", "error": None,
            "request_text": request_text, "user_language": None, "document_type": "", "document_title": "",
            "page_count": 0, "explanation": None, "plan": None, "deadlines": [], "fields": [], "letter": None,
            "verification": None, "steps": [], "cost_usd": 0.0,
            "original_pdf_url": f"/api/documents/{document_id}/original.pdf", "filled_pdf_url": None,
            "final_pdf_url": None, "letter_pdf_url": None, "_meta": {"pdf_path": str(pdf_path), "doc_key": doc_key,
                                                                     "language": language},
        }
        self.store.vaults[task_id] = Vault()
        self.store.save(task)
        return task_id

    def run_async(self, task_id: str) -> None:
        threading.Thread(target=self.run, args=(task_id,), daemon=True).start()

    # ---------------------------------------------------------------- steps
    def _step(self, task: dict, tool: str, title: str, *, model: str | None, location: str) -> dict:
        step = {"id": f"s{len(task['steps']) + 1}", "tool": tool, "title": title, "status": "running", "model": model,
                "location": location, "replayed": False, "cost_usd": 0.0, "detail": None}
        task["steps"].append(step)
        self._emit_step(task, step)
        return step

    def _finish(self, task: dict, step: dict, detail: str, calls=(), status: str = "done") -> None:
        step["status"] = status
        step["detail"] = detail
        if calls:
            step["cost_usd"] = round(sum(c.cost_usd for c in calls), 6)
            step["replayed"] = all(c.replayed for c in calls)
            step["model"] = calls[-1].model
        task["cost_usd"] = round(sum(s["cost_usd"] for s in task["steps"]), 6)
        self._emit_step(task, step)
        log.info("TOOL_EXECUTED task=%s tool=%s status=%s", task["task_id"], step["tool"], status)

    def _emit_step(self, task: dict, step: dict) -> None:
        self.store.emit(task["task_id"], {"type": "step", "step": dict(step), "task_cost_usd": task["cost_usd"]})

    # ---------------------------------------------------------------- main loop
    def run(self, task_id: str) -> None:
        task = self.store.get(task_id)
        meta = task["_meta"]
        step = None
        try:
            step = self._step(task, "read_document", "Reading the document", model="PyMuPDF / Tesseract", location="local")
            doc = read_document(Path(meta["pdf_path"]))
            task["page_count"] = doc.page_count
            step["model"] = "Tesseract OCR" if doc.method == "tesseract-ocr" else "PyMuPDF text layer"
            self._finish(task, step, f"{doc.page_count} page(s), {len(doc.fields)} form fields found")
            log.info("DOCUMENT_PROCESSED task=%s method=%s", task_id, doc.method)

            info = self.privacy.info()
            step = self._step(task, "redact_pii", "Protecting personal information",
                              model=info["model"] or info["label"], location="local")
            vault = self.store.vaults[task_id]
            redacted_text = self.privacy.redact(doc.text, vault)
            redacted_request = self.privacy.redact(task["request_text"], vault)
            self._finish(task, step, f"{len(vault.items)} personal values replaced with placeholders on this device")
            log.info("PII_REDACTED task=%s count=%d", task_id, len(vault.items))

            step = self._step(task, "understand_request", "Understanding your request", model="local language ID",
                              location="local")
            chosen = meta.get("language") or "auto"
            user_lang = lang(chosen) if chosen != "auto" else (detect_language(task["request_text"]) or lang("en"))
            task["user_language"] = {"code": user_lang["code"], "name": user_lang["name"]}
            self._finish(task, step, f"Language: {user_lang['name']}")

            ctx = TaskContext(task_id, task, vault, doc, Path(meta["pdf_path"]).read_bytes(), redacted_text,
                              redacted_request, meta["doc_key"], user_lang)
            self.store.contexts[task_id] = ctx

            step = self._step(task, "plan", "Planning next steps", model=self.router.settings.wonder_model, location="cloud")
            fields_summary = ", ".join(f"{f.name} ({f.label}, {f.kind})" for f in doc.fields)
            plan, calls = make_plan(self.router, task_id=task_id, redacted_text=redacted_text,
                                    redacted_request=redacted_request, fields_summary=fields_summary,
                                    language_name=user_lang["english_name"], doc_key=meta["doc_key"])
            ctx.intent = plan.intent
            task["document_type"], task["document_title"] = plan.document_type, ctx.vault.restore(plan.document_title)
            ordered = enforce_plan_invariants(plan, bool(doc.fields), self.max_steps)
            reasons = {a.tool: a.reason for a in plan.actions}
            task["plan"] = {"document_type": plan.document_type, "intent": plan.intent,
                            "actions": [{"tool": t, "reason": reasons.get(t, "Required by PaperPilot safety rules")}
                                        for t in ordered]}
            self._finish(task, step, f"{len(ordered)} actions planned", calls)

            for tool in ordered:
                if tool == "ask_user_confirmation":
                    break
                if task["cost_usd"] >= self.task_cost_cap:
                    raise BudgetExceeded("This task reached its cost limit. Review what is ready so far.")
                if tool == "verify_form":
                    self._verify(task, ctx)
                    continue
                fn, title, role = TOOLS[tool]
                model = self.router.settings.spark_model if role == "spark" else None
                step = self._step(task, tool, title, model=model or "local", location="cloud" if role else "local")
                outcome = fn(self.router, ctx)
                if tool == "fill_form":
                    self._render_filled(task, ctx)
                self._finish(task, step, outcome.detail, outcome.calls)

            step = self._step(task, "ask_user_confirmation", "Waiting for your review and confirmation",
                              model=None, location="local")
            step["status"] = "waiting"
            step["detail"] = "Nothing is finalized until you confirm."
            self._emit_step(task, step)
            task["status"] = "awaiting_confirmation"
            self.store.save(task)
            self.store.emit(task_id, {"type": "done", "task": public_task(task)})
        except (UnreadableDocument, ModelUnavailable, BudgetExceeded, DemoCacheMiss, PrivacyViolation,
                StructuredOutputError) as exc:
            self._fail(task, step, str(exc))
        except Exception:  # never leak stack traces (or document content) to the UI
            log.exception("TASK_FAILED task=%s", task_id)
            self._fail(task, step, "Something went wrong while processing this document. Please try again.")

    def _fail(self, task: dict, step: dict | None, message: str) -> None:
        if step and step["status"] == "running":
            self._finish(task, step, message, status="error")
        task["status"], task["error"] = "error", message
        self.store.save(task)
        self.store.emit(task["task_id"], {"type": "error", "message": message})

    def _verify(self, task: dict, ctx: TaskContext) -> None:
        step = self._step(task, "verify_form", "Verifying the filled form", model=self.router.settings.wonder_model,
                          location="cloud")
        filled = [{"name": n, "value": v["value"], "confidence": v["confidence"]} for n, v in ctx.raw_fills.items()]
        result, calls = verify(self.router, task_id=task["task_id"], redacted_text=ctx.redacted_text,
                               redacted_request=ctx.redacted_request, filled=filled, intent=ctx.intent,
                               doc_key=ctx.doc_key)
        checks = {c.name: c.model_dump() for c in result.fields}
        _sync_fields(ctx, checks)
        # Deterministic local check: what the PDF actually stores must equal what we meant to write.
        problems = self._render_filled(task, ctx)
        issues = [ctx.vault.restore(i) for i in result.issues] + [f"Field '{p}' could not be written to the PDF" for p in problems]
        task["verification"] = {"overall_confidence": result.overall_confidence,
                                "summary": ctx.vault.restore(result.summary), "issues": issues}
        flagged = sum(1 for f in task["fields"] if f["needs_review"])
        self._finish(task, step, f"{round(result.overall_confidence * 100)}% overall, {flagged} field(s) to review", calls)
        log.info("VERIFICATION_COMPLETED task=%s flagged=%d", task["task_id"], flagged)

    def _render_filled(self, task: dict, ctx: TaskContext) -> list[str]:
        values = {f["name"]: f["value"] for f in task["fields"]}
        pdf = self.filler.fill_acroform(ctx.pdf_bytes, values)
        out = self.outputs / f"{task['task_id']}_filled.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(pdf)
        task["filled_pdf_url"] = f"/api/tasks/{task['task_id']}/filled.pdf"
        log.info("FORM_FILLED task=%s", task["task_id"])
        return self.filler.validate_output(pdf, values)

    # ---------------------------------------------------------------- user actions
    def update_fields(self, task_id: str, values: dict[str, str]) -> dict:
        task = self.store.get(task_id)
        ctx = self.store.contexts[task_id]
        for f in task["fields"]:
            if f["name"] in values:
                f["value"], f["needs_review"], f["confidence"] = str(values[f["name"]]), False, 1.0
                f["note"] = "Edited by you"
        self._render_filled(task, ctx)
        self.store.save(task)
        return task


def public_task(task: dict) -> dict:
    return {k: v for k, v in task.items() if not k.startswith("_")}
