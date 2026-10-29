"""Deadline reminders: SQLite rows + RFC 5545 .ics export."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.db.database import Database, now_iso


def _row(r: dict) -> dict:
    try:
        days = (date.fromisoformat(r["date"]) - date.today()).days
    except ValueError:
        days = None
    return {"id": r["id"], "title": r["title"], "date": r["date"], "description": r["description"] or "",
            "task_id": r["task_id"], "days_remaining": days}


def add_deadline(db: Database, title: str, day: str, description: str = "", task_id: str | None = None) -> dict:
    date.fromisoformat(day)  # validate
    cur = db.execute("INSERT INTO deadlines (title, date, description, task_id, created_at) VALUES (?,?,?,?,?)",
                     (title[:200], day, description[:1000], task_id, now_iso()))
    return _row(db.query("SELECT * FROM deadlines WHERE id=?", (cur.lastrowid,))[0])


def list_deadlines(db: Database) -> list[dict]:
    return [_row(r) for r in db.query("SELECT * FROM deadlines ORDER BY date ASC, id ASC")]


def delete_deadline(db: Database, deadline_id: int) -> bool:
    return db.execute("DELETE FROM deadlines WHERE id=?", (deadline_id,)).rowcount > 0


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def to_ics(items: list[dict]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PaperPilot//Deadlines//EN", "CALSCALE:GREGORIAN"]
    for d in items:
        start = date.fromisoformat(d["date"])
        lines += ["BEGIN:VEVENT", f"UID:paperpilot-{d['id']}@paperpilot.local", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(start + timedelta(days=1)).strftime('%Y%m%d')}",
                  f"SUMMARY:{_esc(d['title'])}", f"DESCRIPTION:{_esc(d['description'])}",
                  "BEGIN:VALARM", "TRIGGER:-P2D", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(d['title'])}", "END:VALARM",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
