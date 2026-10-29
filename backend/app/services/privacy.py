"""Local PII detection + redaction.

Text is redacted on this machine into stable placeholders ([NAME_1], [ACCOUNT_1], ...) before
any cloud call. The placeholder -> original mapping (the "vault") never leaves the process;
values are restored locally only when rendering the user's own PDF/letter.

Two engines behind one interface:
  * GlimmerDetector: Muse Glimmer (open weights) served locally via an OpenAI-compatible
    server such as Ollama / llama.cpp / vLLM. Its spans are merged with the rules engine.
  * RulesDetector: deterministic regex + label rules. Always available, no GPU needed.
The engine actually used is reported to the UI; the fallback is never labelled as Glimmer.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import httpx

log = logging.getLogger("paperpilot.privacy")

TYPE_LABELS = {
    "NAME": "Name", "ADDRESS": "Address", "PHONE": "Phone number", "EMAIL": "Email",
    "ACCOUNT": "Account number", "ID": "ID / case number", "DOB": "Date of birth",
}


@dataclass
class Span:
    value: str
    type: str


_STREET = r"\d{1,5}\s+(?:[A-Z][a-zA-Z]+\s+){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|Way|Court|Ct|Place|Pl)\b\.?"
_UNIT = r"(?:,?\s+(?:Apt|Apartment|Unit|Suite|#)\.?\s*[\w-]+)?"
_CITY = r"(?:,\s*[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)?"
_DATE = r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|[A-Z][a-z]+\.? \d{1,2},? \d{4})"
_PERSON = r"[A-Z][a-z]+(?:[ -][A-Z][a-z]+){1,3}"

RULES: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("ADDRESS", re.compile(_STREET + _UNIT + _CITY)),
    ("PHONE", re.compile(r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}\b")),
    ("ID", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("DOB", re.compile(r"(?i:date of birth|dob|born)\s*[:\-]?\s*(" + _DATE + ")")),
    ("ACCOUNT", re.compile(r"(?i:account|acct|customer|meter)\s*(?i:number|no\.?|#|id)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9-]{5,})")),
    ("ID", re.compile(r"(?i:case|client|member|application)\s*(?i:id|number|no\.?|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9-]{4,})")),
    ("NAME", re.compile(r"(?:(?i:name|customer|applicant|account holder|full name)\s*:\s*|\b(?:Mr|Ms|Mrs|Mx|Dr)\.?\s+"
                       r"|(?i:my name is|i am|i'm|me llamo|mi nombre es|je m'appelle)\s+)(" + _PERSON + ")")),
]
# Words that look like names after labels but are not personal names.
_NOT_NAMES = {"Customer Service", "Account Number", "Service Address", "Billing Dispute", "Energy Assistance"}


class RulesDetector:
    mode = "rules"
    label = "Local rules fallback"
    model = None

    def detect(self, text: str) -> list[Span]:
        spans: list[Span] = []
        for typ, pat in RULES:
            for m in pat.finditer(text):
                value = (m.group(1) if m.groups() else m.group(0)).strip(" ,.")
                if typ == "NAME" and (value in _NOT_NAMES or len(value) < 4):
                    continue
                if typ == "PHONE" and sum(c.isdigit() for c in value) < 10:
                    continue
                spans.append(Span(value, typ))
        return spans


class GlimmerDetector:
    """Muse Glimmer running locally (Ollama / llama.cpp / vLLM, OpenAI-compatible). Never a cloud call."""
    mode = "glimmer"
    label = "Muse Glimmer · open weights, local"

    PROMPT = (
        "Find every piece of personal data in the document. Return JSON {\"items\": [{\"value\": exact substring,"
        " \"type\": one of NAME, ADDRESS, PHONE, EMAIL, ACCOUNT, ID, DOB}]}. Do not include organisations,"
        " amounts, or deadlines. Document:\n\n"
    )

    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.rules = RulesDetector()

    def available(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/models", timeout=2.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def detect(self, text: str) -> list[Span]:
        body = {"model": self.model, "temperature": 1.0, "top_p": 0.95,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": self.PROMPT + text}]}
        r = httpx.post(f"{self.base_url}/chat/completions", json=body, timeout=self.timeout)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        items = json.loads(content).get("items", [])
        spans = [Span(i["value"].strip(), i["type"].upper()) for i in items
                 if isinstance(i, dict) and i.get("value") and i.get("type", "").upper() in TYPE_LABELS
                 and i["value"].strip() in text]
        # Union with the deterministic rules so structured identifiers are never missed.
        return spans + self.rules.detect(text)


@dataclass
class VaultItem:
    placeholder: str
    type: str
    original: str


@dataclass
class Vault:
    """Local-only placeholder <-> original mapping for one document/task."""
    items: dict[str, VaultItem] = field(default_factory=dict)  # placeholder -> item
    _by_value: dict[str, str] = field(default_factory=dict)  # normalized original -> placeholder
    _counters: dict[str, int] = field(default_factory=dict)

    def placeholder_for(self, value: str, typ: str) -> str:
        key = " ".join(value.split()).lower()
        if key in self._by_value:
            return self._by_value[key]
        n = self._counters.get(typ, 0) + 1
        self._counters[typ] = n
        ph = f"[{typ}_{n}]"
        self._by_value[key] = ph
        self.items[ph] = VaultItem(ph, typ, value)
        return ph

    def originals(self) -> list[str]:
        return [i.original for i in self.items.values()]

    def restore(self, text: str) -> str:
        for ph, item in self.items.items():
            text = text.replace(ph, item.original)
        return text

    def leaked_values(self, payload: str) -> int:
        """How many raw values from this vault appear in a serialized payload."""
        flat = " ".join(payload.split())
        count = 0
        for item in self.items.values():
            needles = {item.original, " ".join(item.original.split())}
            if any(n and (n in payload or n in flat) for n in needles):
                count += 1
        return count


class PrivacyEngine:
    def __init__(self, mode: str = "rules", glimmer_base_url: str = "", glimmer_model: str = ""):
        self.rules = RulesDetector()
        self.detector: RulesDetector | GlimmerDetector = self.rules
        if mode == "local":
            g = GlimmerDetector(glimmer_base_url, glimmer_model)
            if g.available():
                self.detector = g
            else:
                log.warning("Glimmer local server not reachable at %s; using rules fallback", glimmer_base_url)

    def info(self) -> dict:
        d = self.detector
        return {"mode": d.mode, "label": d.label, "model": d.model}

    def redact(self, text: str, vault: Vault) -> str:
        try:
            spans = self.detector.detect(text)
        except Exception:  # Glimmer hiccup must never let raw text through
            log.warning("Glimmer detection failed; using rules fallback for this document")
            self.detector = self.rules
            spans = self.rules.detect(text)
        # Register spans (longest names first) so "Mr. Herrera Molina" reuses the full name's placeholder,
        # then also mask bare surnames of detected full names ("Ms. Okafor").
        for s in sorted(spans, key=lambda s: (s.type != "NAME", -len(s.value))):
            if s.type == "NAME":
                full = next((i for i in vault.items.values() if i.type == "NAME" and i.original.endswith(" " + s.value)), None)
                if full:
                    vault._by_value.setdefault(s.value.lower(), full.placeholder)
                    continue
            vault.placeholder_for(s.value, s.type)
        for item in list(vault.items.values()):
            if item.type == "NAME" and " " in item.original:
                surname = item.original.split()[-1]
                if len(surname) > 2:
                    vault._by_value.setdefault(surname.lower(), item.placeholder)
        return apply_vault(text, vault)


def apply_vault(text: str, vault: Vault) -> str:
    """Replace every known original (longest first, whitespace-tolerant) with its placeholder."""
    pairs = sorted(((orig, ph) for orig, ph in vault._by_value.items()), key=lambda p: -len(p[0]))
    for orig_norm, ph in pairs:
        words = [re.escape(w) for w in orig_norm.split()]
        if not words:
            continue
        pattern = re.compile(r"(?<![\w])" + r"\s+".join(words) + r"(?![\w])", re.IGNORECASE)
        text = pattern.sub(ph, text)
    return text
