import hashlib
import html
import re
import unicodedata

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_COMPANY_SUFFIXES = {
    "inc", "llc", "ltd", "limited", "pvt", "private", "gmbh", "corp", "corporation",
    "co", "plc", "ag", "sa", "bv", "pte",
}

IT_KEYWORDS = (
    "engineer", "developer", "software", "data", "machine learning", "ml ", "ai ", " ai",
    "scientist", "devops", "sre", "backend", "back end", "frontend", "front end", "full stack",
    "fullstack", "cloud", "security", "architect", "python", "java", "react", "node", "llm",
    "research", "platform", "programmer", "analytics", "qa ", "sdet", "mlops", "nlp",
    "agentic", "genai", "generative ai", "ai agent",
)


def strip_html(raw: str | None) -> str:
    """Convert (possibly double-escaped) HTML into readable plain text."""
    if not raw:
        return ""
    text = html.unescape(raw)
    if "&lt;" in text or "&gt;" in text:  # Greenhouse double-escapes content
        text = html.unescape(text)
    text = re.sub(r"<(?:br|/p|/li|/div|/h\d)\s*/?>", "\n", text, flags=re.I)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def normalize(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9+#\s]", " ", value)
    return _WS.sub(" ", value).strip()


def normalize_company(name: str | None) -> str:
    words = [w for w in normalize(name).split() if w not in _COMPANY_SUFFIXES]
    return " ".join(words)


def make_dedupe_key(company: str, title: str, location: str) -> str:
    raw = "|".join([normalize_company(company), normalize(title), normalize(location)])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def is_it_job(title: str, extra: str = "") -> bool:
    haystack = f" {normalize(title)} {normalize(extra)} "
    return any(k in haystack for k in IT_KEYWORDS)
