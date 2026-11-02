"""Extract required years of experience from job text.

Rule: never invent. If nothing is confidently found the result is `not_specified`.
"""
import re
from dataclasses import dataclass


@dataclass
class ExperienceResult:
    minimum: float | None
    maximum: float | None
    status: str  # specified | fresher | not_specified
    evidence: str | None = None


# Filter buckets: name -> (low, high). Overlap matching is used against job min/max.
EXPERIENCE_BUCKETS: dict[str, tuple[float, float]] = {
    "fresher": (0, 0),
    "0-1": (0, 1),
    "1-2": (1, 2),
    "2-4": (2, 4),
    "4-6": (4, 6),
    "6-8": (6, 8),
    "8-10": (8, 10),
    "10+": (10, 1000),
}

_NUM = r"(?<![\d.])(\d{1,2})(?!\d)"
_YEARS = r"(?:years?|yrs?)\b"

_RANGE = re.compile(rf"{_NUM}\s*(?:-|–|—|to)\s*{_NUM}\s*\+?\s*{_YEARS}", re.I)
_PLUS = re.compile(rf"{_NUM}\s*\+\s*{_YEARS}", re.I)
_MIN = re.compile(
    rf"(?:minimum|min\.?|at least|atleast|more than|over)\s*(?:of\s*)?{_NUM}\s*\+?\s*{_YEARS}", re.I
)
_SINGLE = re.compile(rf"{_NUM}\s*{_YEARS}(?:'s|’s)?\s*(?:of\s*)?(?:[\w-]+\s+){{0,3}}?experience", re.I)
_EXP_FIRST = re.compile(rf"experience\s*(?:of|:|-|required)?\s*(?:minimum\s*)?{_NUM}\s*\+?\s*{_YEARS}", re.I)
_FRESHER = re.compile(
    r"\bfreshers?\b|\bno (?:prior |previous )?(?:work )?experience (?:is )?(?:required|needed|necessary)\b|"
    r"\b0\s*(?:years?|yrs?)\b",
    re.I,
)

_MAX_PLAUSIBLE = 40


def extract_experience(text: str | None) -> ExperienceResult:
    if not text:
        return ExperienceResult(None, None, "not_specified")

    m = _RANGE.search(text)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        if lo <= hi <= _MAX_PLAUSIBLE:
            return ExperienceResult(lo, hi, "specified", m.group(0))

    for pattern in (_PLUS, _MIN, _EXP_FIRST, _SINGLE):
        m = pattern.search(text)
        if m:
            lo = float(m.group(1))
            if lo <= _MAX_PLAUSIBLE:
                return ExperienceResult(lo, None, "specified", m.group(0))

    m = _FRESHER.search(text)
    if m:
        return ExperienceResult(0.0, 0.0, "fresher", m.group(0))

    return ExperienceResult(None, None, "not_specified")
