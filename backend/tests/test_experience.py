import pytest

from app.services.experience import extract_experience


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Looking for a Python developer with 2–4 years of experience.", (2, 4, "specified")),
        ("2 to 4 years experience in backend", (2, 4, "specified")),
        ("Requires 3+ years of Python", (3, None, "specified")),
        ("Minimum 5 years in cloud engineering", (5, None, "specified")),
        ("At least 6 yrs hands-on", (6, None, "specified")),
        ("You have 5 years of experience building APIs", (5, None, "specified")),
        ("Experience: 4 years", (4, None, "specified")),
        ("0-1 years, freshers welcome", (0, 1, "specified")),
        ("Freshers welcome to apply", (0, 0, "fresher")),
        ("No prior experience required", (0, 0, "fresher")),
        ("8-10 yrs", (8, 10, "specified")),
    ],
)
def test_extracts_expected_ranges(text, expected):
    r = extract_experience(text)
    assert (r.minimum, r.maximum, r.status) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "We are a growing company building developer tools.",
        "Founded in 2012, we have 500 employees across 10 offices.",
        "Great culture, 25 days holiday",
    ],
)
def test_never_invents_experience(text):
    r = extract_experience(text)
    assert r.status == "not_specified"
    assert r.minimum is None and r.maximum is None


def test_range_beats_fresher_mention():
    r = extract_experience("2-4 years of experience. Freshers please do not apply.")
    assert (r.minimum, r.maximum) == (2, 4)
