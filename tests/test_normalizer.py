import pytest

from core.normalizer import (
    clean_text, parse_experience, parse_notice, parse_location,
    split_skills, seniority_level, headline_experience_claim, canonical_value,
)


@pytest.mark.parametrize("raw, expected_value, expected_flag", [
    ("3", 3.0, None),
    ("2.5", 2.5, None),
    ("five years", 5.0, None),
    ("-2", None, "experience_negative"),
    ("", None, "experience_missing"),
])
def test_parse_experience(raw, expected_value, expected_flag):
    value, flags = parse_experience(raw)
    assert value == expected_value
    assert (expected_flag in flags) if expected_flag else (flags == [])


NOTICE_TABLE = [
    ("Immediate", 0, "ok"), ("Available immediately", 0, "ok"), ("2 weeks notice", 14, "ok"),
    ("1 month", 30, "ok"), ("30 days notice", 30, "ok"), ("45 days", 45, "ok"),
    ("60 days", 60, "ok"), ("2 months", 60, "ok"), ("90 days notice", 90, "ok"),
    ("Negotiable", None, "negotiable"), ("starts in 2027", None, "far_future"), ("", None, "missing"),
]


@pytest.mark.parametrize("raw, days, kind", NOTICE_TABLE)
def test_parse_notice(raw, days, kind):
    assert parse_notice(raw) == (days, kind)


@pytest.mark.parametrize("raw, city, country", [
    ("Sharjah,UAE", "Sharjah", "UAE"),
    ("Sharjah, UAE", "Sharjah", "UAE"),
    ("Riyadh, Saudi Arabia", "Riyadh", "Saudi Arabia"),
    ("Alexandria,Egypt", "Alexandria", "Egypt"),
    ("ksa", None, "Saudi Arabia"),
])
def test_parse_location(raw, city, country):
    loc, flags = parse_location(raw)
    assert loc == {"city": city, "country": country}
    assert flags == []


def test_parse_location_empty():
    loc, flags = parse_location("")
    assert loc == {"city": None, "country": None}
    assert flags == ["location_missing"]


def test_clean_text_html_markup():
    raw = "<b>HR Business Partner</b>, Emirates Group (Dubai)<br/>2019-Present: managed employee relations.&nbsp;"
    text, flags = clean_text(raw)
    assert "<" not in text and ">" not in text
    assert "html_markup" in flags


def test_clean_text_mojibake():
    text, flags = clean_text("Customer support specialist with Ã©xperience in SaaS")
    assert "encoding_artifact" in flags


def test_clean_text_dash_is_null():
    assert clean_text("-") == (None, [])


SENIORITY_TABLE = [
    ("Finance Manager with strong FP&A", "", 2.0),
    ("Senior analyst", "", 1.5),
    ("Finance leader with 8 years", "Financial Controller, Some Co", 2.0),
    ("Finance leader with 8 years", "", None),
    ("Junior developer", "", 0.0),
    ("Talent Acquisition Specialist", "", 1.0),
    ("Legal counsel with 15 years", "", 2.0),
    ("Recent graduate seeking opportunities", "", 0.0),
    ("Customer support specialist", "", 1.0),
    ("Sr. DevOps Engineer", "", 1.5),
    ("HR Business Partner", "", 2.0),
]


@pytest.mark.parametrize("headline, past_roles, expected", SENIORITY_TABLE)
def test_seniority_level(headline, past_roles, expected):
    assert seniority_level(headline, past_roles) == expected


def test_headline_experience_claim():
    assert headline_experience_claim("Legal counsel with 15 years in UAE commercial law") == 15
    assert headline_experience_claim("No number here") is None


def test_split_skills_dedupe_preserves_order():
    assert split_skills("SQL, Python, sql, -, Tableau") == ["SQL", "Python", "Tableau"]


def test_canonical_value_location_comma_space_equivalence():
    assert canonical_value("location", "Riyadh,Saudi Arabia") == canonical_value("location", "Riyadh, Saudi Arabia")


def test_headline_field_contradiction_on_real_data(candidates):
    by_id = {c["candidate_id"]: c for c in candidates}
    assert "headline_experience_conflict" in by_id["C128"]["flags"]
