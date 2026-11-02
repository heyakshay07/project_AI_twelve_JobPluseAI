import re

COUNTRY_KEYWORDS: dict[str, list[str]] = {
    "India": ["india", "pune", "bangalore", "bengaluru", "hyderabad", "mumbai", "chennai", "delhi",
              "noida", "gurgaon", "gurugram", "kolkata", "ahmedabad"],
    "United States": ["united states", "usa", "u.s.", "new york", "san francisco", "seattle", "austin",
                      "california", "boston", "chicago", "los angeles", "remote us", "remote - us", "us only"],
    "United Kingdom": ["united kingdom", "uk", "england", "london", "manchester", "scotland"],
    "Canada": ["canada", "toronto", "vancouver", "montreal", "ottawa"],
    "Germany": ["germany", "deutschland", "berlin", "munich", "hamburg", "frankfurt", "cologne", "stuttgart"],
    "France": ["france", "paris"],
    "Netherlands": ["netherlands", "amsterdam", "rotterdam"],
    "Australia": ["australia", "sydney", "melbourne", "brisbane"],
    "Singapore": ["singapore"],
    "United Arab Emirates": ["uae", "dubai", "abu dhabi", "united arab emirates"],
    "Japan": ["japan", "tokyo"],
    "Ireland": ["ireland", "dublin"],
}

_COUNTRY_PATTERNS = {
    country: re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(k) for k in kws) + r")(?![a-z])", re.I)
    for country, kws in COUNTRY_KEYWORDS.items()
}


def guess_country(location: str | None) -> str | None:
    if not location:
        return None
    for country, pattern in _COUNTRY_PATTERNS.items():
        if pattern.search(location):
            return country
    return None


_REMOTE_DESC = re.compile(r"fully remote|100% remote|remote[- ]first|work from home|work-from-home", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.I)
_REMOTE_WORD = re.compile(r"\bremote\b", re.I)


def detect_workplace(title: str, location: str, description: str) -> str:
    """remote | hybrid | unknown. We never guess 'onsite' without evidence from the source."""
    head = f"{title} {location}"
    if _HYBRID.search(head):
        return "hybrid"
    if _REMOTE_WORD.search(head):
        return "remote"
    if _HYBRID.search(description[:2000]):
        return "hybrid"
    if _REMOTE_DESC.search(description[:2000]):
        return "remote"
    return "unknown"
