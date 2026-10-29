import pytest

from app.services.model_router import (BudgetExceeded, DemoCacheMiss, ModelRouter, ModelUnavailable, TaskKind,
                                       TransientError)
from tests.conftest import FakeTransport

MSG = [{"role": "user", "content": "hello"}]


def test_routes_planning_to_wonder_and_reading_to_spark(settings, db):
    r = ModelRouter(settings, db, transport=FakeTransport(lambda b: "{}"))
    assert r.model_for(TaskKind.PLAN) == "muse-wonder-1.0"
    assert r.model_for(TaskKind.VERIFY) == "muse-wonder-1.0"
    assert r.model_for(TaskKind.EXPLAIN) == "muse-spark-1.3"
    assert r.model_for(TaskKind.FILL) == "muse-spark-1.3"
    assert r.model_for(TaskKind.TRANSCRIBE) == "muse-voice-transcribe-1.0"


def test_logs_tokens_and_cost(settings, db):
    t = FakeTransport(lambda b: "hi")
    res = ModelRouter(settings, db, transport=t).chat(TaskKind.EXPLAIN, MSG, task_id="t1")
    assert res.text == "hi" and not res.replayed
    assert res.cost_usd == pytest.approx(1000 * 1.25 / 1e6 + 200 * 4.25 / 1e6)
    assert db.total_spend() == pytest.approx(res.cost_usd)
    assert t.requests[0]["model"] == "muse-spark-1.3"


def test_retries_with_exponential_backoff(settings, db):
    calls = {"n": 0}

    def flaky(body):
        calls["n"] += 1
        return TransientError("HTTP 429") if calls["n"] < 3 else "ok"

    sleeps = []
    settings.retry_base_delay_s = 0.5
    r = ModelRouter(settings, db, transport=FakeTransport(flaky), sleep=sleeps.append)
    assert r.chat(TaskKind.EXPLAIN, MSG).text == "ok"
    assert sleeps == [0.5, 1.0]


def test_gives_up_after_max_retries(settings, db):
    r = ModelRouter(settings, db, transport=FakeTransport(lambda b: TransientError("timeout")), sleep=lambda s: None)
    with pytest.raises(ModelUnavailable):
        r.chat(TaskKind.EXPLAIN, MSG)


def test_budget_cap_blocks_before_sending(settings, db):
    settings.budget_cap_usd = 0.001
    t = FakeTransport(lambda b: "ok")
    r = ModelRouter(settings, db, transport=t)
    with pytest.raises(BudgetExceeded):
        r.chat(TaskKind.PLAN, MSG, max_output_tokens=2000)
    assert t.requests == []
    assert r.budget()["remaining_usd"] == pytest.approx(0.001)


def test_budget_blocked_once_spent(settings, db):
    db.add_usage("x", "muse-spark-1.3", "explain", 0, 0, 100.0, replayed=False)
    r = ModelRouter(settings, db, transport=FakeTransport(lambda b: "ok"))
    assert r.budget()["blocked"]
    with pytest.raises(BudgetExceeded):
        r.chat(TaskKind.EXPLAIN, MSG)


def test_record_then_replay_same_code_path(settings, db):
    settings.record_demo_cache = True
    ModelRouter(settings, db, transport=FakeTransport(lambda b: "recorded")).chat(
        TaskKind.EXPLAIN, MSG, scenarios=["explain:doc1:en"])
    settings.demo_mode, settings.model_api_key = True, ""
    t = FakeTransport(lambda b: "network!")
    r = ModelRouter(settings, db, transport=t)
    exact = r.chat(TaskKind.EXPLAIN, MSG)
    assert exact.text == "recorded" and exact.replayed
    reworded = r.chat(TaskKind.EXPLAIN, [{"role": "user", "content": "different words"}], scenarios=["explain:doc1:en"])
    assert reworded.text == "recorded"
    assert t.requests == []  # demo mode never touches the network
    assert db.total_spend() == pytest.approx(1000 * 1.25 / 1e6 + 200 * 4.25 / 1e6)  # only the real call counts


def test_demo_cache_miss_is_explicit(settings, db):
    settings.demo_mode = True
    with pytest.raises(DemoCacheMiss):
        ModelRouter(settings, db).chat(TaskKind.EXPLAIN, MSG)


def test_transcribe_parses_transcript_and_bills_per_second(settings, db):
    t = FakeTransport()
    wav = b"RIFF" + b"\0" * 4 + b"WAVE" + b"\0" * 16 + (32000).to_bytes(4, "little") + b"\0" * 12 + b"\0" * 96000
    res = ModelRouter(settings, db, transport=t).transcribe(wav)
    assert res.text == "Necesito ayuda con esta carta"
    assert res.cost_usd == pytest.approx(3 * 0.18 / 3600, rel=1e-3)
    assert t.multipart[0]["audio"][2] == "audio/wav"
