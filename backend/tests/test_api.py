import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(demo_settings):
    return TestClient(create_app(demo_settings))


def wait(client, task_id, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        task = client.get(f"/api/tasks/{task_id}").json()
        if task["status"] != "running":
            return task
        time.sleep(0.1)
    raise AssertionError("agent did not finish")


def start(client, sample="utility_dispute", request=None, language="auto"):
    samples = {s["id"]: s for s in client.get("/api/samples").json()}
    doc = client.post("/api/documents/from-sample", json={"sample_id": sample}).json()
    assert doc["page_count"] == 2
    req = request if request is not None else samples[sample]["suggested_request"]
    task_id = client.post("/api/agent/run", json={"document_id": doc["document_id"], "request_text": req,
                                                   "language": language}).json()["task_id"]
    return doc, wait(client, task_id)


def test_health_reports_demo_mode_and_honest_privacy_engine(client):
    h = client.get("/api/health").json()
    assert h["demo_mode"] is True
    assert h["privacy_engine"]["mode"] == "rules" and "Glimmer" not in h["privacy_engine"]["label"]
    assert h["budget"]["cap_usd"] == 100


def test_demo_end_to_end_hindi_utility_dispute(client):
    doc, task = start(client)
    assert task["status"] == "awaiting_confirmation", task["error"]
    assert task["user_language"]["code"] == "hi"
    assert "बिल" in task["explanation"]["summary"]
    assert task["deadlines"][0]["date"] == "2026-11-03"
    assert "Amara Okafor" in task["letter"]["body"]  # restored locally
    assert all(s["replayed"] for s in task["steps"] if s["location"] == "cloud")
    reason = next(f for f in task["fields"] if f["name"] == "dispute_reason")
    assert reason["needs_review"] and reason["rect"] and reason["page"] == 1

    events = client.get(f"/api/agent/events/{task['task_id']}").text
    assert '"type": "step"' in events and '"type": "done"' in events

    priv = client.get(f"/api/privacy/{task['task_id']}").json()
    assert priv["raw_pii_sent"] == 0 and priv["protected_count"] >= 5
    assert "Amara Okafor" not in priv["sanitized_excerpt"] and "[NAME_1]" in priv["sanitized_excerpt"]
    assert len(priv["cloud_requests"]) >= 5

    assert client.get(f"/api/tasks/{task['task_id']}/filled/pages/1.png").headers["content-type"] == "image/png"
    edited = client.patch(f"/api/tasks/{task['task_id']}/fields",
                          json={"values": {"dispute_reason": "I was away for most of September."}}).json()
    reason = next(f for f in edited["fields"] if f["name"] == "dispute_reason")
    assert reason["value"].startswith("I was away") and not reason["needs_review"]

    assert client.post(f"/api/tasks/{task['task_id']}/confirm", json={"confirmed": False}).status_code == 400
    done = client.post(f"/api/tasks/{task['task_id']}/confirm", json={"confirmed": True}).json()
    assert done["status"] == "confirmed"
    assert client.get(done["final_pdf_url"]).headers["content-type"] == "application/pdf"
    assert client.get(done["letter_pdf_url"]).status_code == 200

    deadlines = client.get("/api/deadlines").json()
    assert deadlines and deadlines[0]["task_id"] == task["task_id"]
    ics = client.get("/api/deadlines/export.ics").text
    assert "BEGIN:VCALENDAR" in ics and "DTSTART;VALUE=DATE:20261103" in ics


def test_demo_spanish_benefit_application_without_letter(client):
    _, task = start(client, "benefit_application")
    assert task["user_language"]["code"] == "es"
    assert task["letter"] is None and "draft_response" not in [a["tool"] for a in task["plan"]["actions"]]
    assert "invierno" in task["explanation"]["summary"]


def test_deadline_crud(client):
    d = client.post("/api/deadlines", json={"title": "Rent renewal", "date": "2026-12-01", "description": ""}).json()
    assert client.get(f"/api/deadlines/{d['id']}/ics").status_code == 200
    assert client.delete(f"/api/deadlines/{d['id']}").status_code == 200
    assert client.post("/api/deadlines", json={"title": "x", "date": "tomorrow"}).status_code == 422


def test_upload_validation(client):
    bad = client.post("/api/documents/upload", files={"file": ("evil.exe", b"MZ...", "application/octet-stream")})
    assert bad.status_code == 400 and "PDF" in bad.json()["detail"]
    voice = client.post("/api/voice/transcribe", files={"audio": ("a.webm", b"notawav", "audio/webm")})
    assert voice.status_code == 400
