"""Process-wide service container (built once in main.create_app, swappable in tests)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.agents.executor import AgentRunner, TaskStore
from app.config import Settings
from app.db.database import Database
from app.services.model_router import ModelRouter, Transport
from app.services.privacy import PrivacyEngine

SAMPLES = {
    "utility_dispute": {
        "title": "Utility high-bill notice + dispute form",
        "description": "A power company says this month's bill is 3x normal. Dispute it before the deadline.",
        "suggested_request": "मुझे यह बिल समझ नहीं आ रहा। इस महीने का बिल बहुत ज़्यादा आया है। कृपया इसका विरोध करने "
                             "और मीटर की जांच के लिए जवाब तैयार करने में मेरी मदद करें।",
    },
    "benefit_application": {
        "title": "Winter energy assistance application",
        "description": "A county letter says you may qualify for a heating credit. Apply before the deadline.",
        "suggested_request": "Recibí esta carta. Quiero solicitar la ayuda de energía. Calentamos la casa con "
                             "electricidad y somos cuatro en casa.",
    },
}


@dataclass
class AppState:
    settings: Settings
    db: Database
    router: ModelRouter
    privacy: PrivacyEngine
    store: TaskStore
    runner: AgentRunner
    sample_hashes: dict[str, str]


def build_state(settings: Settings, transport: Transport | None = None, db: Database | None = None) -> AppState:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = db or Database(settings.data_dir / "paperpilot.db")
    router = ModelRouter(settings, db, transport=transport)
    privacy = PrivacyEngine(settings.glimmer_mode, settings.glimmer_base_url, settings.glimmer_model)
    store = TaskStore(db)
    runner = AgentRunner(router, privacy, store, outputs_dir=settings.data_dir / "outputs",
                         max_steps=settings.max_agent_steps, task_cost_cap=settings.task_cost_cap_usd)
    hashes = {}
    for sid in SAMPLES:
        p = settings.samples_dir / f"{sid}.pdf"
        if p.exists():
            hashes[hashlib.sha256(p.read_bytes()).hexdigest()] = sid
    return AppState(settings, db, router, privacy, store, runner, hashes)
