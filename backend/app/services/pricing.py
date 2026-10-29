"""Meta Model API prices (USD per 1M tokens), from dev.meta.ai/docs/pricing-rate-limits (checked 2026-10-29)."""
from __future__ import annotations

TOKEN_PRICES: dict[str, tuple[float, float]] = {
    # model id: (input per 1M, output per 1M) -- Standard mode
    "muse-spark-1.3": (1.25, 4.25),
    "muse-spark-1.2": (1.25, 4.25),
    "muse-spark-1.1": (1.25, 4.25),
    "muse-wonder-1.0": (4.00, 20.00),
    # Contributor mode (content may be used for training; not the default here)
    "muse-spark-1.3-contributor": (0.10, 0.20),
    "muse-spark-1.2-contributor": (0.10, 0.20),
}
TRANSCRIBE_PRICE_PER_SECOND = 0.18 / 3600  # $0.18 per hour of audio, billed in whole seconds
UNKNOWN_MODEL_PRICE = (4.00, 20.00)  # be conservative for budget checks


def token_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = TOKEN_PRICES.get(model, UNKNOWN_MODEL_PRICE)
    return round(input_tokens * inp / 1_000_000 + output_tokens * out / 1_000_000, 6)


def transcribe_cost(audio_seconds: float) -> float:
    return round(int(audio_seconds) * TRANSCRIBE_PRICE_PER_SECOND, 6)
