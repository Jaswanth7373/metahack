"""Central model router: every Meta Model API call goes through here.

Responsibilities: pick the model for a task kind, enforce the budget cap, retry with
exponential backoff, log tokens + cost, replay/record the demo cache, and run the
outgoing privacy guard on every serialized payload *before* it can leave the machine.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol

import httpx

from app.config import Settings
from app.db.database import Database
from app.services.pricing import UNKNOWN_MODEL_PRICE, TOKEN_PRICES, token_cost, transcribe_cost

log = logging.getLogger("paperpilot.router")


class TaskKind(str, Enum):
    PLAN = "plan"
    VERIFY = "verify"
    EXPLAIN = "explain"
    EXTRACT_DEADLINES = "extract_deadlines"
    FILL = "fill"
    DRAFT = "draft"
    TRANSCRIBE = "transcribe"


class BudgetExceeded(RuntimeError):
    pass


class ModelUnavailable(RuntimeError):
    pass


class DemoCacheMiss(RuntimeError):
    pass


class PrivacyViolation(RuntimeError):
    """Raised when an outgoing payload still contains a raw PII value. The request is not sent."""


class Transport(Protocol):
    def post_json(self, url: str, headers: dict, body: dict, timeout: float) -> dict: ...
    def post_multipart(self, url: str, headers: dict, files: dict, timeout: float) -> dict: ...


class TransientError(RuntimeError):
    """Retryable transport failure (429, 5xx, timeout, connection error)."""


class HttpxTransport:
    def post_json(self, url: str, headers: dict, body: dict, timeout: float) -> dict:
        return self._send(lambda c: c.post(url, headers=headers, json=body), timeout)

    def post_multipart(self, url: str, headers: dict, files: dict, timeout: float) -> dict:
        return self._send(lambda c: c.post(url, headers=headers, files=files), timeout)

    @staticmethod
    def _send(fn, timeout: float) -> dict:
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = fn(client)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise TransientError(type(exc).__name__) from exc
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientError(f"HTTP {resp.status_code}")
        if resp.status_code >= 400:
            # Do not echo the body: it may contain the (redacted) prompt.
            raise ModelUnavailable(f"Model API rejected the request (HTTP {resp.status_code}).")
        return resp.json()


@dataclass
class ChatResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    replayed: bool


@dataclass
class TranscribeResult:
    text: str
    model: str
    cost_usd: float
    replayed: bool


class DemoCache:
    """Response cache. Exact key = hash of the full request; scenario key = stable task+document id
    so a demo replays even if the spoken request is worded differently."""

    def __init__(self, root: Path):
        self.root = root

    @staticmethod
    def exact_key(body: dict) -> str:
        canon = json.dumps(body, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canon.encode()).hexdigest()[:32]

    def _path(self, kind: str, key: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in key)
        return self.root / kind / f"{safe}.json"

    def get(self, exact: str, scenarios: list[str]) -> dict | None:
        for kind, key in [("exact", exact)] + [("scenario", s) for s in scenarios]:
            p = self._path(kind, key)
            if p.exists():
                return json.loads(p.read_text())
        return None

    def put(self, exact: str, scenario: str | None, entry: dict) -> None:
        targets = [("exact", exact)] + ([("scenario", scenario)] if scenario else [])
        for kind, key in targets:
            p = self._path(kind, key)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(entry, ensure_ascii=False, indent=2))


# Guard signature: (task_id, serialized_payload) -> number of raw PII values found in it.
OutgoingGuard = Callable[[str | None, str], int]


class ModelRouter:
    ROUTES = {
        TaskKind.PLAN: "wonder",
        TaskKind.VERIFY: "wonder",
        TaskKind.EXPLAIN: "spark",
        TaskKind.EXTRACT_DEADLINES: "spark",
        TaskKind.FILL: "spark",
        TaskKind.DRAFT: "spark",
        TaskKind.TRANSCRIBE: "transcribe",
    }

    def __init__(self, settings: Settings, db: Database, transport: Transport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.settings = settings
        self.db = db
        self.transport = transport or HttpxTransport()
        self.cache = DemoCache(settings.demo_cache_dir)
        self.sleep = sleep
        self.guards: list[OutgoingGuard] = []

    # ------------------------------------------------------------------ helpers
    def model_for(self, kind: TaskKind) -> str:
        role = self.ROUTES[kind]
        return {"wonder": self.settings.wonder_model, "spark": self.settings.spark_model,
                "transcribe": self.settings.transcribe_model}[role]

    def add_guard(self, guard: OutgoingGuard) -> None:
        self.guards.append(guard)

    def budget(self) -> dict:
        used = self.db.total_spend()
        cap = self.settings.budget_cap_usd
        return {"cap_usd": cap, "used_usd": round(used, 6), "remaining_usd": round(max(cap - used, 0), 6),
                "blocked": used >= cap}

    def _check_budget(self, model: str, body_chars: int, max_output_tokens: int) -> None:
        used = self.db.total_spend()
        inp, out = TOKEN_PRICES.get(model, UNKNOWN_MODEL_PRICE)
        worst_case = (body_chars / 3) * inp / 1e6 + max_output_tokens * out / 1e6
        if used + worst_case > self.settings.budget_cap_usd:
            raise BudgetExceeded("Budget limit reached. No additional paid AI requests will be made.")

    def _run_guards(self, task_id: str | None, model: str, kind: TaskKind, payload: str, replayed: bool) -> None:
        found = sum(g(task_id, payload) for g in self.guards)
        self.db.add_privacy_event(task_id, model, kind.value, len(payload), found, blocked=found > 0)
        if found:
            log.warning("PRIVACY_BLOCKED kind=%s model=%s raw_values=%d", kind.value, model, found)
            raise PrivacyViolation("Blocked an outgoing request that still contained personal data.")

    def _with_retries(self, fn: Callable[[], dict]) -> dict:
        attempts = max(1, self.settings.max_retries)
        for i in range(attempts):
            try:
                return fn()
            except TransientError as exc:
                if i == attempts - 1:
                    raise ModelUnavailable("AI service temporarily unavailable.") from exc
                delay = self.settings.retry_base_delay_s * (2 ** i)
                log.info("MODEL_RETRY attempt=%d delay=%.2fs reason=%s", i + 1, delay, exc)
                self.sleep(delay)
        raise ModelUnavailable("AI service temporarily unavailable.")  # pragma: no cover

    # ------------------------------------------------------------------ chat
    def chat(self, kind: TaskKind, messages: list[dict], *, task_id: str | None = None,
             schema: dict | None = None, schema_name: str = "result", scenarios: list[str] | None = None,
             max_output_tokens: int = 2000, reasoning_effort: str = "low") -> ChatResult:
        model = self.model_for(kind)
        body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_output_tokens,
                                "reasoning_effort": reasoning_effort}
        if schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": schema_name, "schema": schema}}
        payload = json.dumps(body, ensure_ascii=False)
        # The privacy guard runs on every path, including replays, so the audit covers demo mode too.
        self._run_guards(task_id, model, kind, payload, replayed=self.settings.is_demo)

        exact = self.cache.exact_key(body)
        scenarios = scenarios or []
        if self.settings.is_demo:
            entry = self.cache.get(exact, scenarios)
            if entry is None:
                raise DemoCacheMiss("This input is not in the demo cache. Add an API key to run in real mode.")
            usage = entry.get("usage", {})
            itok, otok = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
            cost = token_cost(model, itok, otok)  # what this call costs in real mode; nothing is charged
            self.db.add_usage(task_id, model, kind.value, itok, otok, cost, replayed=True)
            log.info("MODEL_CALLED kind=%s model=%s replayed=1", kind.value, model)
            return ChatResult(entry["content"], model, itok, otok, cost, replayed=True)

        if not self.settings.model_api_key:
            raise ModelUnavailable("No MODEL_API_KEY configured. Set it in .env or enable DEMO_MODE.")
        self._check_budget(model, len(payload), max_output_tokens)
        headers = {"Authorization": f"Bearer {self.settings.model_api_key}"}
        url = f"{self.settings.model_api_base}/chat/completions"
        data = self._with_retries(lambda: self.transport.post_json(url, headers, body, self.settings.request_timeout_s))
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelUnavailable("The AI service returned an unexpected response.") from exc
        usage = data.get("usage") or {}
        itok, otok = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
        cost = token_cost(model, itok, otok)
        self.db.add_usage(task_id, model, kind.value, itok, otok, cost, replayed=False)
        log.info("MODEL_CALLED kind=%s model=%s in=%d out=%d cost=%.6f", kind.value, model, itok, otok, cost)
        if self.settings.record_demo_cache:
            self.cache.put(exact, scenarios[0] if scenarios else None,
                           {"kind": kind.value, "model": model, "content": text, "usage": usage})
        return ChatResult(text, model, itok, otok, cost, replayed=False)

    # ------------------------------------------------------------------ voice
    def transcribe(self, wav_bytes: bytes, *, task_id: str | None = None,
                   scenarios: list[str] | None = None) -> TranscribeResult:
        model = self.model_for(TaskKind.TRANSCRIBE)
        settings_json = {"model": model, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}
        exact = hashlib.sha256(wav_bytes).hexdigest()[:32]
        if self.settings.is_demo:
            entry = self.cache.get(exact, scenarios or [])
            if entry is None:
                raise DemoCacheMiss("Voice is replayed from the demo cache in Demo Mode; type your request instead.")
            self.db.add_usage(task_id, model, "transcribe", 0, 0, 0.0, replayed=True)
            return TranscribeResult(entry["content"], model, 0.0, replayed=True)
        if not self.settings.model_api_key:
            raise ModelUnavailable("No MODEL_API_KEY configured. Set it in .env or enable DEMO_MODE.")
        seconds = _wav_seconds(wav_bytes)
        if self.db.total_spend() + transcribe_cost(seconds) > self.settings.budget_cap_usd:
            raise BudgetExceeded("Budget limit reached. No additional paid AI requests will be made.")
        headers = {"Authorization": f"Bearer {self.settings.model_api_key}", "Accept": "application/json"}
        files = {"request": (None, json.dumps(settings_json), "application/json"),
                 "audio": ("request.wav", wav_bytes, "audio/wav")}
        url = f"{self.settings.model_api_base}/asr/transcribe"
        data = self._with_retries(lambda: self.transport.post_multipart(url, headers, files, self.settings.request_timeout_s))
        text = data.get("transcript", "")
        if data.get("audioDurationMs"):
            seconds = data["audioDurationMs"] / 1000
        cost = transcribe_cost(seconds)
        self.db.add_usage(task_id, model, "transcribe", 0, 0, cost, replayed=False)
        if self.settings.record_demo_cache:
            self.cache.put(exact, (scenarios or [None])[0], {"kind": "transcribe", "model": model, "content": text})
        return TranscribeResult(text, model, cost, replayed=False)


def _wav_seconds(wav: bytes) -> float:
    """Duration of a PCM WAV from its header (byte rate at offset 28); 0 if unparsable."""
    try:
        byte_rate = int.from_bytes(wav[28:32], "little")
        return max(len(wav) - 44, 0) / byte_rate if byte_rate else 0.0
    except Exception:
        return 0.0
