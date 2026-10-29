"""Tiny SQLite layer. Raw PII is only ever stored locally (tasks), never in usage logs."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, filename TEXT, path TEXT, sha256 TEXT, page_count INTEGER, created_at TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, document_id TEXT, status TEXT, task_json TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, date TEXT, description TEXT, task_id TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, task_id TEXT, model TEXT, kind TEXT,
    input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, replayed INTEGER
);
CREATE TABLE IF NOT EXISTS privacy_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, task_id TEXT, model TEXT, kind TEXT,
    chars INTEGER, raw_pii_found INTEGER, blocked INTEGER
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # --- usage -------------------------------------------------------------
    def add_usage(self, task_id, model, kind, input_tokens, output_tokens, cost_usd, replayed) -> None:
        self.execute(
            "INSERT INTO usage (ts, task_id, model, kind, input_tokens, output_tokens, cost_usd, replayed)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (now_iso(), task_id, model, kind, input_tokens, output_tokens, cost_usd, int(replayed)),
        )

    def total_spend(self) -> float:
        row = self.query("SELECT COALESCE(SUM(cost_usd),0) AS s FROM usage WHERE replayed=0")
        return float(row[0]["s"])

    def recent_usage(self, limit: int = 50) -> list[dict]:
        return self.query("SELECT * FROM usage ORDER BY id DESC LIMIT ?", (limit,))

    # --- privacy audit (counts only, never values) --------------------------
    def add_privacy_event(self, task_id, model, kind, chars, raw_pii_found, blocked) -> None:
        self.execute(
            "INSERT INTO privacy_events (ts, task_id, model, kind, chars, raw_pii_found, blocked)"
            " VALUES (?,?,?,?,?,?,?)",
            (now_iso(), task_id, model, kind, chars, raw_pii_found, int(blocked)),
        )

    # --- tasks ---------------------------------------------------------------
    def save_task(self, task_id: str, document_id: str, status: str, task: dict) -> None:
        self.execute(
            "INSERT INTO tasks (id, document_id, status, task_json, created_at, updated_at) VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET status=excluded.status, task_json=excluded.task_json,"
            " updated_at=excluded.updated_at",
            (task_id, document_id, status, json.dumps(task), now_iso(), now_iso()),
        )

    def load_task(self, task_id: str) -> dict | None:
        rows = self.query("SELECT task_json FROM tasks WHERE id=?", (task_id,))
        return json.loads(rows[0]["task_json"]) if rows else None
