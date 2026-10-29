"""Runtime configuration, loaded from environment / the repo-root .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(REPO_DIR / ".env"), extra="ignore")

    # Meta Model API (OpenAI-compatible). Never hardcode the key.
    model_api_key: str = ""
    model_api_base: str = "https://api.meta.ai/v1"
    spark_model: str = "muse-spark-1.3"
    wonder_model: str = "muse-wonder-1.0"
    transcribe_model: str = "muse-voice-transcribe-1.0"

    # Cost control
    budget_cap_usd: float = 100.0
    task_cost_cap_usd: float = 0.50
    max_agent_steps: int = 10

    # None = auto: demo mode is on when no API key is configured.
    demo_mode: bool | None = None
    record_demo_cache: bool = False

    # Privacy engine: "local" = Muse Glimmer via a local OpenAI-compatible server
    # (Ollama / llama.cpp / vLLM); "rules" = deterministic regex + rules fallback.
    glimmer_mode: Literal["local", "rules"] = "rules"
    glimmer_base_url: str = "http://localhost:11434/v1"
    glimmer_model: str = "muse-glimmer"

    request_timeout_s: float = 60.0
    max_retries: int = 3
    retry_base_delay_s: float = 0.5
    max_upload_mb: int = 10

    data_dir: Path = BACKEND_DIR / "data"
    demo_cache_dir: Path = BACKEND_DIR / "demo_cache"
    samples_dir: Path = REPO_DIR / "samples"

    @property
    def is_demo(self) -> bool:
        if self.demo_mode is None:
            return not self.model_api_key
        return self.demo_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
