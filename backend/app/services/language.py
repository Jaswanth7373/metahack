"""Zero-cost local language detection (script ranges + stopwords). Used before any model call."""
from __future__ import annotations

import re

NAMES = {"en": "English", "es": "Español", "fr": "Français", "pt": "Português", "de": "Deutsch", "it": "Italiano",
         "hi": "हिन्दी", "bn": "বাংলা", "ta": "தமிழ்", "te": "తెలుగు", "kn": "ಕನ್ನಡ", "mr": "मराठी", "ar": "العربية",
         "he": "עברית", "th": "ไทย", "zh": "中文", "ja": "日本語", "ko": "한국어", "vi": "Tiếng Việt", "tl": "Tagalog",
         "id": "Bahasa Indonesia", "tr": "Türkçe", "nl": "Nederlands", "pl": "Polski"}
ENGLISH_NAMES = {"en": "English", "es": "Spanish", "fr": "French", "pt": "Portuguese", "de": "German", "it": "Italian",
                 "hi": "Hindi", "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "kn": "Kannada", "mr": "Marathi",
                 "ar": "Arabic", "he": "Hebrew", "th": "Thai", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
                 "vi": "Vietnamese", "tl": "Tagalog", "id": "Indonesian", "tr": "Turkish", "nl": "Dutch", "pl": "Polish"}

SCRIPTS = [("hi", 0x0900, 0x097F), ("bn", 0x0980, 0x09FF), ("ta", 0x0B80, 0x0BFF), ("te", 0x0C00, 0x0C7F),
           ("kn", 0x0C80, 0x0CFF), ("ar", 0x0600, 0x06FF), ("he", 0x0590, 0x05FF), ("th", 0x0E00, 0x0E7F),
           ("ja", 0x3040, 0x30FF), ("ko", 0xAC00, 0xD7AF), ("zh", 0x4E00, 0x9FFF)]
STOPWORDS = {
    "en": "the and to is i this my please what do need help with have not",
    "es": "el la de que y en los por para una con mi esta necesito ayuda quiero somos",
    "fr": "le la les de et des que pour une avec mon cette besoin aide je veux",
    "pt": "o a de que e do da para uma com meu esta preciso ajuda quero não",
    "de": "der die das und ist ich nicht mit ein eine bitte brauche hilfe",
    "it": "il la di che e per una con mio questa ho bisogno aiuto voglio",
}


def lang(code: str) -> dict:
    return {"code": code, "name": NAMES.get(code, code), "english_name": ENGLISH_NAMES.get(code, code)}


def detect_language(text: str) -> dict | None:
    counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        for code, lo, hi in SCRIPTS:
            if lo <= cp <= hi:
                counts[code] = counts.get(code, 0) + 1
    if counts:
        code = max(counts, key=counts.get)
        if code == "zh" and counts.get("ja"):
            code = "ja"
        return lang(code)
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    if not words:
        return None
    scores = {c: sum(w in set(sw.split()) for w in words) for c, sw in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    return lang(best) if scores[best] > 0 else None
