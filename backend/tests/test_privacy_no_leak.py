"""The critical privacy test: intercept every outgoing cloud request and assert no raw PII is in it."""
import pytest

from app.agents.executor import AgentRunner, TaskStore
from app.config import REPO_DIR
from app.services.model_router import ModelRouter, PrivacyViolation, TaskKind
from app.services.privacy import PrivacyEngine
from tests.conftest import FakeTransport

RAW = {
    "utility_dispute": ["Amara Okafor", "Okafor", "48 Willow Creek Lane", "7731-0042-8815", "(541) 555-0148",
                        "amara.okafor@example.com"],
    "benefit_application": ["Luis Herrera Molina", "Herrera Molina", "1207 Cedar Hollow Road", "MC-EA-55120",
                            "04/12/1979", "(541) 555-0193", "luis.herrera@example.com"],
}
# The user also says personal details out loud; those must be redacted too.
SPOKEN = "My name is Amara Okafor, call me on (541) 555-0148 or amara.okafor@example.com. Please dispute this bill."


def run(settings, db, sample, request):
    t = FakeTransport()
    router = ModelRouter(settings, db, transport=t)
    store = TaskStore(db)
    runner = AgentRunner(router, PrivacyEngine("rules"), store, outputs_dir=settings.data_dir / "out",
                         max_steps=10, task_cost_cap=1.0)
    tid = runner.create_task("d1", REPO_DIR / "samples" / f"{sample}.pdf", sample, request, "en")
    runner.run(tid)
    return t, store.get(tid), store


@pytest.mark.parametrize("sample", ["utility_dispute", "benefit_application"])
def test_no_raw_pii_in_any_outgoing_request(settings, db, sample):
    t, task, store = run(settings, db, sample, SPOKEN)
    assert task["status"] == "awaiting_confirmation", task["error"]
    assert len(t.requests) >= 5  # plan, explain, deadlines, fill, verify (+ draft)
    payload = t.payload_text()
    for value in RAW[sample] + ["Amara Okafor", "(541) 555-0148", "amara.okafor@example.com"]:
        assert value not in payload, f"raw PII leaked to cloud: {value}"
    for value in store.vaults[task["task_id"]].originals():
        assert value not in payload
    assert "[NAME_1]" in payload  # the model works with placeholders instead
    # ...and the user still gets their real values back, restored locally.
    values = {f["name"]: f["value"] for f in task["fields"]}
    name_field = "customer_name" if sample == "utility_dispute" else "applicant_name"
    assert values[name_field] == RAW[sample][0]


def test_guard_blocks_a_payload_that_contains_raw_pii(settings, db):
    t, task, store = run(settings, db, "utility_dispute", "help")
    sent = len(t.requests)
    router = ModelRouter(settings, db, transport=t)
    router.add_guard(store.guard)
    with pytest.raises(PrivacyViolation):
        router.chat(TaskKind.EXPLAIN, [{"role": "user", "content": "Amara Okafor owes 7731-0042-8815"}],
                    task_id=task["task_id"])
    assert len(t.requests) == sent  # never sent


def test_audit_log_records_zero_raw_values(settings, db):
    _, task, _ = run(settings, db, "benefit_application", SPOKEN)
    rows = db.query("SELECT raw_pii_found FROM privacy_events WHERE task_id=?", (task["task_id"],))
    assert rows and sum(r["raw_pii_found"] for r in rows) == 0
