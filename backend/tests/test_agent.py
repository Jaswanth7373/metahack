import json

import pytest

from app.agents.executor import AgentRunner, TaskStore
from app.agents.planner import enforce_plan_invariants
from app.agents.schemas import Plan
from app.agents.structured import StructuredOutputError, structured_call
from app.config import REPO_DIR
from app.services.model_router import ModelRouter, TaskKind
from app.services.privacy import PrivacyEngine
from tests.conftest import FakeTransport, fixture_responder


def plan(*tools):
    return Plan(document_type="x", document_title="x", intent="x",
                actions=[{"tool": t, "reason": "r"} for t in tools])


def test_invariants_confirmation_last_and_verify_after_fill():
    order = enforce_plan_invariants(plan("ask_user_confirmation", "fill_form", "draft_response"), True, 10)
    assert order[0] == "explain_document"
    assert order[-1] == "ask_user_confirmation"
    assert order.index("verify_form") > order.index("fill_form")
    assert order.count("ask_user_confirmation") == 1


def test_invariants_skip_fill_without_fields_and_cap_length():
    order = enforce_plan_invariants(plan("fill_form", "verify_form", "add_deadline"), False, 10)
    assert "fill_form" not in order and "verify_form" not in order
    assert order.index("extract_deadline") < order.index("add_deadline")
    assert len(enforce_plan_invariants(plan("extract_deadline", "fill_form", "draft_response"), True, 3)) == 3


def test_invalid_plan_is_rejected_by_schema():
    with pytest.raises(Exception):
        Plan.model_validate({"document_type": "x", "document_title": "x", "intent": "x",
                             "actions": [{"tool": "delete_everything", "reason": "r"}]})


def test_invalid_json_gets_one_repair_retry(settings, db):
    good = json.dumps({"document_type": "a", "document_title": "b", "intent": "c",
                       "actions": [{"tool": "explain_document", "reason": "r"}]})
    replies = iter(["not json {", good])
    t = FakeTransport(lambda b: next(replies))
    out, calls = structured_call(ModelRouter(settings, db, transport=t), TaskKind.PLAN, "sys", "user", Plan,
                                 task_id=None, scenarios=[])
    assert out.intent == "c" and len(calls) == 2
    assert "failed validation" in t.requests[1]["messages"][-1]["content"]


def test_invalid_twice_fails_gracefully(settings, db):
    t = FakeTransport(lambda b: '{"actions": "nope"}')
    with pytest.raises(StructuredOutputError):
        structured_call(ModelRouter(settings, db, transport=t), TaskKind.PLAN, "s", "u", Plan, task_id=None, scenarios=[])

    store = TaskStore(db)
    runner = AgentRunner(ModelRouter(settings, db, transport=t), PrivacyEngine("rules"), store,
                         outputs_dir=settings.data_dir, max_steps=10, task_cost_cap=1.0)
    tid = runner.create_task("d", REPO_DIR / "samples" / "utility_dispute.pdf", "utility_dispute", "help", "en")
    runner.run(tid)
    task = store.get(tid)
    assert task["status"] == "error" and "invalid Plan" in task["error"]
    assert "Traceback" not in task["error"]
    assert store.events[tid][-1]["type"] == "error"


def run_sample(settings, db, sample="utility_dispute", lang="hi", request="मुझे मदद चाहिए"):
    t = FakeTransport(fixture_responder)
    store = TaskStore(db)
    runner = AgentRunner(ModelRouter(settings, db, transport=t), PrivacyEngine("rules"), store,
                         outputs_dir=settings.data_dir / "out", max_steps=10, task_cost_cap=1.0)
    tid = runner.create_task("d", REPO_DIR / "samples" / f"{sample}.pdf", sample, request, lang)
    runner.run(tid)
    return store.get(tid), store, t


def test_full_run_pauses_for_confirmation_with_steps_and_costs(settings, db):
    task, store, t = run_sample(settings, db)
    assert task["status"] == "awaiting_confirmation"
    tools = [s["tool"] for s in task["steps"]]
    assert tools[:4] == ["read_document", "redact_pii", "understand_request", "plan"]
    assert tools[-1] == "ask_user_confirmation" and task["steps"][-1]["status"] == "waiting"
    assert {s["location"] for s in task["steps"]} == {"local", "cloud"}
    assert task["cost_usd"] > 0 and task["user_language"]["code"] == "hi"
    assert task["final_pdf_url"] is None  # nothing finalized without the user
    assert "Hindi" in t.requests[1]["messages"][0]["content"]  # explanation requested in the user's language
    assert store.events[task["task_id"]][-1]["type"] == "done"


def test_signature_and_declaration_are_never_filled_by_ai(settings, db):
    task, _, _ = run_sample(settings, db, "benefit_application", "es", "Somos cuatro, calefacción eléctrica")
    by_name = {f["name"]: f for f in task["fields"]}
    assert by_name["signature"]["value"] == "" and by_name["signature"]["needs_review"]
    assert by_name["declaration"]["value"] == "Off" and by_name["declaration"]["needs_review"]
    assert by_name["monthly_income"]["needs_review"]  # flagged by the verifier
    assert by_name["heating_source"]["value"] == "Electricity"


def test_task_cost_cap_stops_the_loop(settings, db):
    t = FakeTransport(fixture_responder)
    store = TaskStore(db)
    runner = AgentRunner(ModelRouter(settings, db, transport=t), PrivacyEngine("rules"), store,
                         outputs_dir=settings.data_dir, max_steps=10, task_cost_cap=0.000001)
    tid = runner.create_task("d", REPO_DIR / "samples" / "utility_dispute.pdf", "utility_dispute", "help", "en")
    runner.run(tid)
    assert store.get(tid)["status"] == "error"
    assert len(t.requests) == 1  # only the planner ran
