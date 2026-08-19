"""Rubric Compiler: free-text guidance -> Guard-validated rubric (D-20)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from core import llm
from core import policy as policy_module
from core.policy import DEFAULT_WEIGHTS, apply_ops, default_rubric, validate_ops


class ReweightOp(BaseModel, extra="forbid"):
    op: Literal["reweight"]
    dimension: Literal["required_skills", "nice_to_have", "experience_fit", "seniority", "location", "availability"]
    new_weight: float


class PromoteDemoteOp(BaseModel, extra="forbid"):
    op: Literal["promote_demote_skill"]
    skill: str
    to_tier: Literal["required", "nice_to_have", "ignore"]


class HardFilterOp(BaseModel, extra="forbid"):
    op: Literal["hard_filter"]
    field: Literal["location_scope", "notice_days_max", "experience_years_min", "experience_years_max", "must_have_skill"]
    value: int | str


class BoostPenaltyOp(BaseModel, extra="forbid"):
    op: Literal["boost_penalty"]
    concept: str
    fields: list[str]
    match_terms: list[str]
    direction: Literal["boost", "penalty"]
    magnitude: float


class SetTopKOp(BaseModel, extra="forbid"):
    op: Literal["set_top_k"]
    value: int


Op = Annotated[
    Union[ReweightOp, PromoteDemoteOp, HardFilterOp, BoostPenaltyOp, SetTopKOp],
    Field(discriminator="op"),
]


class Rejected(BaseModel, extra="forbid"):
    text: str
    reason: Literal["policy_violation", "not_supported", "injection_suspected"]
    closest_supported: str | None = None


class RubricDiff(BaseModel, extra="forbid"):
    operations: list[Op]
    interpretation: str
    rejected_instructions: list[Rejected]


def _build_compiler_prefix(role: dict, vocab: set[str]) -> str:
    pol = policy_module.load_policy()
    parts = [
        llm.load_prompt("compiler"),
        "",
        "## Rendered bounds and context",
        f"Allowed operations: {pol['allowed_operations']}",
        f"Weight bounds: {pol['weight_bounds']}",
        f"Top-k bounds: {pol['top_k_bounds']}",
        f"Hard filter allowed fields: {pol['hard_filter_allowed_fields']}",
        f"Location scope values: {pol['location_scope_values']}",
        f"Boost allowed fields: {pol['boost_allowed_fields']}",
        f"Boost magnitude bounds: {pol['boost_magnitude_bounds']}",
        f"Boost max terms: {pol['boost_max_terms']}",
        f"Banned terms: {pol['banned_terms']}",
        "",
        f"Role: {role}",
        "",
        f"Six scoring dimensions and default weights: {DEFAULT_WEIGHTS}",
        "",
        f"Candidate skill vocabulary ({len(vocab)} tokens): {', '.join(sorted(vocab))}",
    ]
    return "\n".join(parts)


def _unify_compiler_rejections(rejected: list[Rejected]) -> list[dict]:
    return [
        {"text": r.text, "reason": r.reason, "detail": "", "closest_supported": r.closest_supported}
        for r in rejected
    ]


def compile_guidance(role: dict, guidance: str, vocab: set[str], aliases: dict, top_k_default: int) -> dict:
    if not guidance or not guidance.strip():
        return {
            "rubric": default_rubric(top_k_default), "rejected": [], "adjustments": [],
            "ops_accepted": [], "usage": None, "prompt_hash": None,
        }
    prefix = _build_compiler_prefix(role, vocab)
    system_blocks = [{"type": "text", "text": prefix, "cache_control": {"type": "ephemeral"}}]
    user_text = f"<recruiter_guidance>{guidance}</recruiter_guidance>"
    diff, usage = llm.call_structured(system_blocks, user_text, RubricDiff, stage="compiler")
    ops = [op.model_dump() for op in diff.operations]
    accepted, guard_rejected = validate_ops(ops, role, vocab, aliases)
    rubric, adjustments = apply_ops(DEFAULT_WEIGHTS, accepted, top_k_default, diff.interpretation)
    return {
        "rubric": rubric, "rejected": _unify_compiler_rejections(diff.rejected_instructions) + guard_rejected,
        "adjustments": adjustments, "ops_accepted": accepted, "usage": usage, "prompt_hash": llm.prompt_hash("compiler"),
    }
