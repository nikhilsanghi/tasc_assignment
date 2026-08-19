"""Critic: mechanical grounding verification (D-40) - deterministic Python, not an LLM."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import re
import unicodedata

TEN_FIELDS = {
    "headline", "skills", "experience_years", "past_roles", "certifications",
    "education", "projects", "extra_curriculars", "location", "notice_period",
}
SUPERLATIVES = ["best", "perfect", "ideal", "outstanding", "exceptional"]


def norm(s: str) -> str:
    text = unicodedata.normalize("NFC", s or "")
    return re.sub(r"\s+", " ", text).strip().casefold()


def _check_overlaps(analysis: dict, rec: dict, valid_requirements: set[str]) -> list[dict]:
    failures = []
    for overlap in analysis["overlaps"]:
        source_field = overlap["source_field"]
        if source_field not in TEN_FIELDS:
            failures.append({"kind": "bad_source_field", "detail": source_field})
        haystack = rec["normalized_text"].get(source_field, "")
        if norm(overlap["evidence"]) not in haystack:
            failures.append({"kind": "evidence_not_found", "detail": overlap["evidence"]})
        if overlap["requirement"].casefold() not in valid_requirements:
            failures.append({"kind": "bad_requirement", "detail": overlap["requirement"]})
    return failures


def _check_questions(analysis: dict) -> list[dict]:
    questions = analysis["clarifying_questions"]
    failures = []
    if len(questions) != 3:
        failures.append({"kind": "question_count", "detail": str(len(questions))})
    gap_count = sum(1 for q in questions if q["kind"] == "gap")
    data_count = sum(1 for q in questions if q["kind"] == "data")
    if gap_count < 2 or data_count > 1:
        failures.append({"kind": "question_mix", "detail": f"gap={gap_count} data={data_count}"})
    return failures


def _check_superlatives(analysis: dict) -> list[dict]:
    text = (analysis.get("fit_brief") or "").casefold()
    for word in SUPERLATIVES:
        if re.search(rf"\b{word}\b", text):
            return [{"kind": "superlative", "detail": word}]
    return []


def verify(analysis: dict, rec: dict, scored: dict) -> dict:
    valid_requirements = {s.casefold() for s in scored["requirements"]["required"] + scored["requirements"]["nice"]}
    failures = _check_overlaps(analysis, rec, valid_requirements)
    failures += _check_questions(analysis)
    failures += _check_superlatives(analysis)
    checks = 3 * len(analysis["overlaps"]) + 3
    return {"passed": failures == [], "failures": failures, "checks": checks}
