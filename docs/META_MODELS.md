# Meta models in PaperPilot

Checked against Meta's official docs on **2026-10-29**:
[models](https://dev.meta.ai/docs/models), [pricing & rate limits](https://dev.meta.ai/docs/pricing-rate-limits),
[chat completions](https://dev.meta.ai/docs/protocols/chat-completions), [structured output](https://dev.meta.ai/docs/structured-output),
[speech to text](https://dev.meta.ai/docs/speech-to-text), [transcribe API](https://dev.meta.ai/docs/api-reference/voice/transcribe),
[Muse Glimmer deploy](https://dev.meta.ai/docs/muse-glimmer/deploy).
Base URL `https://api.meta.ai/v1`, `Authorization: Bearer $MODEL_API_KEY`, OpenAI-compatible.

## What PaperPilot uses

| Model | Purpose in PaperPilot | Model ID | Endpoint | Input we send | Why this model |
|---|---|---|---|---|---|
| Muse Wonder | Planner + verifier | `muse-wonder-1.0` | `POST /v1/chat/completions` with `response_format: json_schema` | Redacted text only | The two judgment-heavy calls: choosing tools, and checking every filled value against the source. 2 of ~6 calls per task. |
| Muse Spark | Explain, deadlines, fill, draft | `muse-spark-1.3` | `POST /v1/chat/completions` with `response_format: json_schema` | Redacted text only | Fast, cheaper workhorse for ~4 of ~6 calls. Writes the explanation in the user's language. |
| Muse Voice Transcribe | User's spoken request | `muse-voice-transcribe-1.0` | `POST /v1/asr/transcribe` (multipart: `request` JSON + `audio` WAV) | 16 kHz mono 16-bit WAV, encoded in the browser | 25 languages incl. Hindi, Tamil, Kannada, Telugu, Spanish, with code-switching. Real mode only. |
| Muse Glimmer (open weights) | Optional local PII detector | served locally as `muse-glimmer` (Ollama) | Local OpenAI-compatible server, never the cloud | Raw text, on the user's machine | Open weights can see raw text because nothing leaves the device. Runs only when `GLIMMER_MODE=local` and the server answers. Otherwise the rules engine runs, and the UI says so. |

**Not used:** SAM 3.1 (`sam-3.1`, form-region detection) was a stretch goal and was not built. Both sample forms are AcroForms, so field positions come from the PDF itself. The flat-form path (`PDFFormFiller.fill_flat_form`) takes manual coordinate templates. Muse Image (`muse-image-1.0`) has no role in this product.

**Not sent to the cloud:** document images. OCR runs locally with Tesseract and only redacted text is sent. Meta's models accept image input, but sending a photo would also send the personal data in it.

## Prices and limits (from the official pricing page)

| Model ID | Input / 1M | Output / 1M | Cached input / 1M | Rate limit (per team) |
|---|---|---|---|---|
| `muse-spark-1.3` (also 1.2, 1.1) | $1.25 | $4.25 | $0.15 | 3,000 RPM, 4M TPM |
| `muse-spark-1.3-contributor` | $0.10 | $0.20 | $0.002 | 150 RPM, 3M TPM |
| `muse-wonder-1.0` | $4.00 | $20.00 | $0.20 | 3,000 RPM, 4M TPM |
| `muse-voice-transcribe-1.0` | $0.18 per audio hour, billed per whole second | | | 256 concurrent streams, 16,000 per hour |
| `sam-3.1` | $2.50 per 1,000 images | | | 3,000 RPM |
| `muse-image-1.0` | $0.01 per image | | | 150 RPM |

- Contributor mode is about 12x cheaper, but Meta may use your content for training. PaperPilot defaults to Standard mode. Switch with `SPARK_MODEL=muse-spark-1.3-contributor` if you accept that.
- Muse Wonder has no Contributor tier.
- Availability varies by country (see Meta's Geographic Use Policy). Muse Wonder is not available in South Korea.

## API details we rely on

- **Structured output:** `response_format: {"type": "json_schema", "json_schema": {"name", "schema", "strict"}}`, Chat Completions only. PaperPilot validates every response with Pydantic anyway and retries once with the validation error (`backend/app/agents/structured.py`).
- **Reasoning:** `reasoning_effort` accepts `"none"` through `"xhigh"`. `"none"` returns HTTP 400 on Muse Spark. PaperPilot sends `"low"`.
- **Usage:** `usage.prompt_tokens` and `usage.completion_tokens` are priced in `backend/app/services/pricing.py`.
- **Transcription:** the response field is `transcript`. The API has no detected-language field (the model detects the language itself), so PaperPilot identifies the language locally from the transcript's script and common words (`backend/app/services/language.py`).

## Running Muse Glimmer locally (optional)

| Item | Value (from the deploy guide) |
|---|---|
| Weights | `meta-models/Muse-Glimmer-30B` (bf16), `meta-models/Muse-Glimmer-30B-GGUF` (e.g. `Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf`), MLX builds for Apple silicon |
| License | Apache 2.0 according to the hosted-provider listing. The deploy page itself does not state a license, so check the Hugging Face model card. |
| Memory | bf16 needs about 72 GB VRAM. Q4 GGUF is 17–20 GB (about 24 GiB in use at 16K context). MLX needs 48 GB+ unified memory. |
| Runtimes | Ollama ≥ 0.32.7 (`ollama run muse-glimmer`, OpenAI API on `:11434/v1`), llama.cpp ≥ b10353, vLLM, SGLang, Transformers ≥ 5.15 |

```bash
ollama run muse-glimmer          # then in .env:
GLIMMER_MODE=local
GLIMMER_BASE_URL=http://localhost:11434/v1
GLIMMER_MODEL=muse-glimmer
```

On startup PaperPilot checks `GET {GLIMMER_BASE_URL}/models`. If the server does not answer, it uses the rules engine and the UI shows "Local rules fallback". Glimmer's detections are added to the rules engine's results, so structured IDs are always caught.

**Status:** the Glimmer backend is implemented, but it has not been run here. The build machine has no GPU and no Ollama. The demo uses the rules engine and says so.
