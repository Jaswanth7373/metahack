from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.config import REPO_DIR, Settings  # noqa: E402
from app.db.database import Database  # noqa: E402

SCENARIOS = BACKEND / "demo_cache" / "scenario"
SCHEMA_TO_KIND = {"Plan": "plan", "Explanation": "explain", "Deadlines": "deadlines", "FillResult": "fill",
                  "Letter": "draft", "Verification": "verify"}


class FakeTransport:
    """Stands in for the Meta Model API. Records every outgoing request body exactly as it would be sent."""

    def __init__(self, responder=None):
        self.requests: list[dict] = []
        self.multipart: list[dict] = []
        self.responder = responder or fixture_responder

    def post_json(self, url, headers, body, timeout):
        self.requests.append(json.loads(json.dumps(body)))
        content = self.responder(body)
        if isinstance(content, Exception):
            raise content
        return {"choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200}}

    def post_multipart(self, url, headers, files, timeout):
        self.multipart.append(files)
        return {"transcript": "Necesito ayuda con esta carta", "audioDurationMs": 3000}

    def payload_text(self) -> str:
        return "\n".join(json.dumps(r, ensure_ascii=False) for r in self.requests)


def fixture_responder(body: dict) -> str:
    """Answer with the demo fixture that matches this request's schema and document."""
    kind = SCHEMA_TO_KIND[body["response_format"]["json_schema"]["name"]]
    text = json.dumps(body["messages"], ensure_ascii=False)
    doc = "utility_dispute" if "Billing Dispute" in text else "benefit_application"
    candidates = [f"{kind}_{doc}_en.json", f"{kind}_{doc}.json"]
    for c in candidates:
        if (SCENARIOS / c).exists():
            return json.loads((SCENARIOS / c).read_text())["content"]
    raise AssertionError(f"no fixture for {kind}/{doc}")


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(model_api_key="test-key", demo_mode=False, data_dir=tmp_path / "data",
                    demo_cache_dir=tmp_path / "cache", retry_base_delay_s=0.0, budget_cap_usd=100.0,
                    samples_dir=REPO_DIR / "samples", glimmer_mode="rules", _env_file=None)


@pytest.fixture
def demo_settings(tmp_path) -> Settings:
    return Settings(model_api_key="", demo_mode=True, data_dir=tmp_path / "data",
                    demo_cache_dir=BACKEND / "demo_cache", samples_dir=REPO_DIR / "samples",
                    glimmer_mode="rules", _env_file=None)


@pytest.fixture
def db() -> Database:
    return Database(":memory:")
