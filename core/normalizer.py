"""Normalizer: raw CSV rows -> typed values + flags. Never silently fixes dirt."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import html
import json
import re
import unicodedata

from core.paths import DATA
from core.normalizer_tables import (
    WORD_NUMBERS, COUNTRY_ALIASES, ROLE_CITY_COUNTRY, ROLE_SENIORITY_LEVEL, SENIORITY_LADDER,
    HTML_TAG_RE, ENCODING_ARTIFACT_RE, NON_ID_FIELDS,
)


def clean_text(raw: str | None) -> tuple[str | None, list[str]]:
    if not raw or raw == "-":
        return None, []
    flags = []
    stripped = HTML_TAG_RE.sub(" ", raw)
    unescaped = html.unescape(stripped)
    if unescaped != raw:
        flags.append("html_markup")
    text = unicodedata.normalize("NFC", unescaped)
    if ENCODING_ARTIFACT_RE.search(text):
        flags.append("encoding_artifact")
    text = re.sub(r"\s+", " ", text).strip()
    return (text or None), flags


def parse_experience(raw: str | None) -> tuple[float | None, list[str]]:
    if raw is None or not raw.strip():
        return None, ["experience_missing"]
    text = re.sub(r"\s*(years|year|yrs)\s*$", "", raw.strip().casefold()).strip()
    if text == "a":
        return 1.0, []
    if re.match(r"^-?\d+(\.\d+)?$", text):
        value = float(text)
        return (None, ["experience_negative"]) if value < 0 else (value, [])
    if text in WORD_NUMBERS:
        return float(WORD_NUMBERS[text]), []
    return None, ["experience_unparseable"]


def parse_notice(raw: str | None) -> tuple[int | None, str]:
    if raw is None or not raw.strip():
        return None, "missing"
    text = raw.strip().casefold()
    if "immediate" in text:
        return 0, "ok"
    if "negotiable" in text:
        return None, "negotiable"
    if re.match(r"starts in \d{4}", text):
        return None, "far_future"
    for unit, multiplier in (("day", 1), ("week", 7), ("month", 30)):
        m = re.search(rf"(\d+)\s*{unit}", text)
        if m:
            return int(m.group(1)) * multiplier, "ok"
    return None, "unparseable"


def parse_location(raw: str | None) -> tuple[dict, list[str]]:
    if raw is None or not raw.strip():
        return {"city": None, "country": None}, ["location_missing"]
    text = raw.strip()
    if "," in text:
        city_raw, country_raw = text.split(",", 1)
        country_key = country_raw.strip().casefold()
        country = COUNTRY_ALIASES.get(country_key, country_raw.strip() or None)
        return {"city": city_raw.strip() or None, "country": country}, []
    city_key = text.casefold()
    if city_key in COUNTRY_ALIASES:
        return {"city": None, "country": COUNTRY_ALIASES[city_key]}, []
    return {"city": text, "country": None}, []


def split_skills(raw: str | None) -> list[str]:
    if not raw:
        return []
    seen, result = set(), []
    for token in raw.split(","):
        token = token.strip()
        if not token or token == "-":
            continue
        key = token.casefold()
        if key not in seen:
            seen.add(key)
            result.append(token)
    return result


def norm_tokens(skills: list[str]) -> list[str]:
    return [s.casefold() for s in skills]


def seniority_level(headline: str | None, past_roles: str | None) -> float | None:
    title = (past_roles or "").split(",", 1)[0].strip()
    text = f"{headline or ''} {title}".casefold()
    for pattern, value in SENIORITY_LADDER:
        if pattern.search(text):
            return value
    return None


def headline_experience_claim(headline: str | None) -> int | None:
    if not headline:
        return None
    m = re.search(r"(\d+)\+?\s*years", headline)
    return int(m.group(1)) if m else None


def dup_key(headline: str | None, skills_raw: str | None) -> str:
    def _norm(s: str | None) -> str:
        return re.sub(r"\s+", " ", (s or "").strip()).casefold()
    return f"{_norm(headline)}|{_norm(skills_raw)}"


def canonical_value(field: str, raw: str | None) -> str:
    if field == "location":
        loc, _ = parse_location(raw)
        return f"{loc['city'] or ''}|{loc['country'] or ''}"
    return re.sub(r"\s+", " ", (raw or "").strip()).casefold()


def data_quality(rec: dict) -> float:
    non_null = 0
    for field in NON_ID_FIELDS:
        value = (rec.get(field) or "").strip()
        if value and value != "-":
            non_null += 1
    return non_null / 10


def normalize_roles(raw_roles: list[dict]) -> list[dict]:
    out = []
    for row in raw_roles:
        exp_min, exp_max = (int(x) for x in re.findall(r"\d+", row["experience_range"])[:2])
        required = split_skills(row["required_skills"])
        nice = split_skills(row["nice_to_have_skills"])
        city = row["location"].strip()
        out.append({
            "role_id": row["role_id"], "title": row["title"], "department": row["department"],
            "required_skills": required, "nice_to_have": nice,
            "required_norm": norm_tokens(required), "nice_norm": norm_tokens(nice),
            "exp_min": exp_min, "exp_max": exp_max,
            "seniority": row["seniority"], "seniority_level": ROLE_SENIORITY_LEVEL[row["seniority"]],
            "location": {"city": city, "country": ROLE_CITY_COUNTRY.get(city)},
        })
    return out


if __name__ == "__main__":
    from scripts.profile_data import load_csv
    from core.normalizer_records import normalize_all

    cands = normalize_all(load_csv(DATA / "candidate_profiles.csv"))
    roles = normalize_roles(load_csv(DATA / "open_roles.csv"))
    (DATA / "candidates_normalized.json").write_text(json.dumps(cands, sort_keys=True, indent=1))
    (DATA / "roles_normalized.json").write_text(json.dumps(roles, sort_keys=True, indent=1))
    print(f"wrote {len(cands)} candidates, {len(roles)} roles")
