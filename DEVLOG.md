# DEVLOG

## 2026-10-29: Day 1 (one long session)

**Step 0: Meta docs check** (dev.meta.ai, 2026-10-29). Verified IDs: `muse-spark-1.3`, `muse-wonder-1.0`,
`muse-voice-transcribe-1.0`, `sam-3.1`, `muse-image-1.0`. Glimmer is open weights only (not on the Model API).
Prices and limits are in docs/META_MODELS.md. Surprises:
- The transcribe API needs **WAV (16/24 kHz mono PCM)** and returns `transcript` with **no language field**.
  → The browser encodes WAV (no ffmpeg); language is identified locally.
- `reasoning_effort: "none"` returns 400 on Spark → send `"low"`.
- Contributor tier is about 12x cheaper but Meta may use the content for training → not the default, for a privacy product.

**Decisions**
- Local OCR first (Tesseract), never cloud vision on raw photos. Only redacted text goes to the cloud.
- Privacy guard lives in the **router**, so no code path can skip it, demo replays included.
- Safety invariants (explain first, verify after fill, confirmation last, step cap) are enforced in code
  (`enforce_plan_invariants`), not trusted to the planner prompt.
- Signatures and declarations are never filled by AI.
- Deadlines are staged during the run and only written on Confirm ("nothing finalized without confirmation").
- Demo cache: exact request hash, then a scenario key (task + document [+ language]), so a reworded
  request still replays. Same router code path; only the response source changes.
- Port 8010 by default (8000 was taken on the build machine).

**Built:** model router (budget cap, retries, cost log, demo cache, PII guard), privacy engine (rules +
Glimmer interface), document reader, AcroForm/flat PDF filler, planner/executor/verifier + 7 tools,
FastAPI + SSE, React UI (home, timeline, results, privacy center, review, confirm, done, deadlines),
2 fictional samples, demo fixtures, 35 tests.

**Costs so far:** $0.00 (no API key yet; everything ran in demo mode with hand-written fixtures).
Estimated real cost per task is about $0.06 (see README).

**Not done / next**
- [ ] Add MODEL_API_KEY → run both samples in real mode with RECORD_DEMO_CACHE=true; note real costs here.
- [ ] Try voice in real mode on a phone (Hindi + Spanish).
- [ ] Test the Glimmer backend on a machine with ≥ 24 GB VRAM (Ollama `muse-glimmer`).
- [ ] Record the demo video; take screenshots for the README.
- [ ] SAM 3.1 for flat forms (stretch).
