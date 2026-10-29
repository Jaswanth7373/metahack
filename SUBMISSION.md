# PaperPilot: submission

**What did you build?**
PaperPilot is a voice-first, privacy-first paperwork agent. You photograph an official document and say what you need in your own language. It explains the document in that language, plans the next steps, fills the form, drafts the reply letter and saves the deadline. Nothing is final until you confirm.

**What problem does it solve?**
Official paperwork (utility notices, benefit letters, bank, school and rental forms) is hard to read, especially in a second language. It hides deadlines and forms that are easy to get wrong. Missing a deadline means late fees, collections or lost benefits.

**Why is it important?**
The people most affected are often the least able to pay for help: immigrants, older people, people with low literacy. PaperPilot turns "I don't understand this letter" into a completed, checked form and a reminder, in the user's own language.

**What Meta technologies did you use?**
- **Muse Wonder** (`muse-wonder-1.0`): planner (strict JSON plan of tool calls) and verifier (checks each filled value against the source and flags low-confidence fields).
- **Muse Spark** (`muse-spark-1.3`): plain-language explanation in the user's language, deadline extraction, form filling, reply drafting.
- **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`): the spoken request, multilingual.
- **Muse Glimmer** (open weights): optional local PII detector behind the same interface as the rules fallback. The UI labels which one actually ran.
All cloud calls use the Meta Model API's OpenAI-compatible Chat Completions with `json_schema` structured output, through one router that picks the model per task.

**How is it agentic?**
Wonder plans which tools to run for this document and request; the plan differs between documents. An executor runs the tools and streams each step live. Wonder then verifies the result. The agent ends by pausing for human review. Invalid plans get one automatic repair retry. Safety rules live in code: explain first, always verify after filling, confirmation always last, step and cost caps, and signatures and declarations are never filled by AI.

**What makes it technically interesting?**
- A model router with a hard budget cap (checked before sending against a worst-case estimate), exponential-backoff retries, per-call token and cost logging, and a demo cache on the same code path.
- A **privacy guard inside the router** that scans every serialized payload for raw personal values and blocks it, proven by an interception test across full agent runs.
- Local placeholder restoration so the real values reach only the user's own PDF. AcroForm automation with read-back validation.

**How does privacy work?**
OCR and redaction run on the device. Personal data becomes stable placeholders (`[NAME_1]`, `[ACCOUNT_1]`), and the mapping never leaves the machine. The cloud models work only with placeholders. The Privacy Center shows what was protected, the exact text the AI saw, every cloud request, and "0 raw personal values sent", computed from the audit log.

**What did you build during the hackathon?**
Everything in this repository was written during the event, starting 2026-10-29 (see the git history and DEVLOG.md). All sample people, companies, addresses and numbers are fictional.

**How does the demo work?**
Pick the utility-bill sample and speak (or type) a request in Hindi. Watch the agent timeline, read the Hindi explanation, open the Privacy Center, review the side-by-side filled form with the flagged dispute reason, edit it, confirm, and download the form, the letter and the `.ics` reminder.

**What could you build next?**
SAM 3.1 for photographed flat forms, Glimmer as the default on capable devices, spoken replies, and more document types (rent, school, tax).

*PaperPilot is not legal advice. It explains, drafts and fills; the user decides and confirms.*
