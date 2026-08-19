"""Analyst: per-candidate evidence-cited explanation (LLM, one call + up to one regeneration)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from typing import Literal

from pydantic import BaseModel

from core import llm, critic
from core import policy as policy_module

FREE_TEXT_DISPLAY = ["headline", "past_roles", "certifications", "education", "projects", "extra_curriculars"]
RAW_DISPLAY = ["skills", "experience_years", "location", "notice_period"]
SIX_DIMENSIONS_EXPLAINED = {
    "required_skills": "coverage of the role's required skills, matched exact/alias/semantic",
    "nice_to_have": "coverage of the role's nice-to-have skills",
    "experience_fit": "how the candidate's years of experience compare to the role's range",
    "seniority": "how the candidate's seniority level compares to the role's",
    "location": "how close the candidate's location is to the role's",
    "availability": "how soon the candidate could start",
}


class Overlap(BaseModel, extra="forbid"):
    requirement: str
    evidence: str
    source_field: str
    tier: Literal["exact", "alias", "semantic", "inferred"]


class Gap(BaseModel, extra="forbid"):
    requirement: str
    severity: Literal["required", "nice_to_have"]
    note: str


class Question(BaseModel, extra="forbid"):
    text: str
    kind: Literal["gap", "data"]


class AnalystOutput(BaseModel, extra="forbid"):
    candidate_id: str
    overlaps: list[Overlap]
    gaps: list[Gap]
    fit_brief: str
    clarifying_questions: list[Question]
    data_flags: list[str]
    confidence: Literal["high", "medium", "low"]


def build_prefix(role: dict, rubric: dict) -> str:
    policy = policy_module.load_policy()
    parts = [
        llm.load_prompt("analyst"),
        "",
        "## Rendered context",
        f"Policy trust rules: {policy['trust_rules']}",
        "",
        f"Role: {role}",
        "",
        f"Rubric: weights={rubric['weights']}, skill_overrides={rubric['skill_overrides']}, "
        f"hard_filters={rubric['hard_filters']}, boosts={rubric['boosts']}, penalties={rubric['penalties']}, "
        f"interpretation={rubric['interpretation']!r}",
        "",
        f"Six scoring dimensions: {SIX_DIMENSIONS_EXPLAINED}",
        "",
        "Score bands: >=80 strong, 60-79 viable-with-gaps, <60 stretch.",
    ]
    return "\n".join(parts)


def _duplicate_members_block(rec: dict, dup_rows: list[dict]) -> list[str]:
    if not dup_rows:
        return []
    conflicts = rec.get("dup_conflicts", {})
    lines = ["", "<duplicate_members>", f"Conflicting fields across this candidate's duplicate rows: {conflicts}"]
    for row in dup_rows:
        fields = ", ".join(f"{f}={row['raw'].get(f)}" for f in conflicts)
        lines.append(f"- {row['candidate_id']}: {fields}")
    lines.append("</duplicate_members>")
    return lines


def build_user_turn(rec: dict, dup_rows: list[dict], scored: dict, failures: list[dict] | None) -> str:
    parts = ["<candidate_profile>"]
    for field in FREE_TEXT_DISPLAY:
        parts.append(f"{field}: {rec.get(field) or ''}")
    for field in RAW_DISPLAY:
        parts.append(f"{field}: {rec['raw'].get(field, '')}")
    parts.append("</candidate_profile>")
    parts += [
        "", "<deterministic_decomposition>",
        f"subscores: {scored['subscores']}", f"flags: {scored['flags']}",
        f"auto_questions: {scored['auto_questions']}", f"requirements: {scored['requirements']}",
        "</deterministic_decomposition>",
    ]
    parts += _duplicate_members_block(rec, dup_rows)
    if failures:
        parts += ["", "<critic_failures>"] + [f"- {f['kind']}: {f['detail']}" for f in failures] + ["</critic_failures>"]
    return "\n".join(parts)


def _repair(analysis: dict, rec: dict, scored: dict) -> dict:
    valid = {s.casefold() for s in scored["requirements"]["required"] + scored["requirements"]["nice"]}
    kept, dropped = [], []
    for o in analysis["overlaps"]:
        ok_field = o["source_field"] in critic.TEN_FIELDS
        haystack = rec["normalized_text"].get(o["source_field"], "") if ok_field else ""
        ok = ok_field and critic.norm(o["evidence"]) in haystack and o["requirement"].casefold() in valid
        (kept if ok else dropped).append(o)
    analysis = dict(analysis)
    analysis["overlaps"] = kept
    analysis["data_flags"] = list(analysis["data_flags"]) + [f"ungrounded citation removed: {o['evidence']}" for o in dropped]
    return analysis


def analyze(rec: dict, role: dict, rubric: dict, dup_rows: list[dict], scored: dict) -> dict:
    prefix = build_prefix(role, rubric)
    system_blocks = [{"type": "text", "text": prefix, "cache_control": {"type": "ephemeral"}}]
    output, usage = llm.call_structured(system_blocks, build_user_turn(rec, dup_rows, scored, None), AnalystOutput, stage="analyst")
    analysis = output.model_dump()
    verdict = critic.verify(analysis, rec, scored)
    regenerated, usage_regen = False, None
    if not verdict["passed"]:
        regenerated, usage_regen = True, usage
        user_turn2 = build_user_turn(rec, dup_rows, scored, verdict["failures"])
        output2, usage = llm.call_structured(system_blocks, user_turn2, AnalystOutput, stage="analyst")
        analysis = output2.model_dump()
        verdict = critic.verify(analysis, rec, scored)
        if not verdict["passed"]:
            analysis = _repair(analysis, rec, scored)
            unresolved = {"evidence_not_found", "bad_requirement", "bad_source_field"}
            for f in verdict["failures"]:
                if f["kind"] not in unresolved:
                    analysis["data_flags"].append(f"critic_unresolved: {f['kind']}")
            analysis["confidence"] = "low"
    return {
        "analysis": analysis, "critic": verdict, "regenerated": regenerated,
        "usage": usage, "usage_regen": usage_regen, "prompt_hash": llm.prompt_hash("analyst"),
    }
