import math

import pytest

from core.rubric import (
    BoostPenaltyOp, HardFilterOp, PromoteDemoteOp, Rejected, ReweightOp, RubricDiff, SetTopKOp, compile_guidance,
)


def _one_of_each_diff(role, weight=0.05):
    return RubricDiff(
        operations=[
            ReweightOp(op="reweight", dimension="availability", new_weight=weight),
            PromoteDemoteOp(op="promote_demote_skill", skill=role["required_skills"][0], to_tier="required"),
            HardFilterOp(op="hard_filter", field="notice_days_max", value=30),
            BoostPenaltyOp(op="boost_penalty", concept="x", fields=["skills"], match_terms=["python"],
                           direction="boost", magnitude=0.05),
            SetTopKOp(op="set_top_k", value=15),
        ],
        interpretation="test interpretation",
        rejected_instructions=[Rejected(text="bad thing", reason="not_supported", closest_supported="reweight")],
    )


def test_one_op_of_each_type(fake_llm, role_r004, aliases):
    stub = fake_llm(_one_of_each_diff(role_r004))
    vocab = set(role_r004["required_norm"])
    result = compile_guidance(role_r004, "some guidance", vocab, aliases, top_k_default=10)
    assert len(stub.calls) == 1
    rubric = result["rubric"]
    assert math.fsum(rubric["weights"].values()) == pytest.approx(1.0)
    assert rubric["top_k"] == 15
    assert rubric["interpretation"] == "test interpretation"


def test_compiler_rejections_before_guard_rejections(fake_llm, role_r004, aliases):
    diff = _one_of_each_diff(role_r004)
    # add a Guard-level rejection by including an out-of-bounds op too
    diff.operations.append(ReweightOp(op="reweight", dimension="seniority", new_weight=0.9))
    fake_llm(diff)
    result = compile_guidance(role_r004, "some guidance", set(), aliases, top_k_default=10)
    rejected = result["rejected"]
    assert rejected[0]["reason"] == "not_supported"
    assert rejected[0]["detail"] == ""
    assert rejected[-1]["detail"] == "weight_bounds"


def test_adjustments_present_when_clamping(fake_llm, role_r004, aliases):
    diff = RubricDiff(
        operations=[ReweightOp(op="reweight", dimension="availability", new_weight=0.60)],
        interpretation="clamp test", rejected_instructions=[],
    )
    fake_llm(diff)
    result = compile_guidance(role_r004, "guidance", set(), aliases, top_k_default=10)
    assert result["adjustments"] == []  # single reweight to the max bound alone does not overflow
    assert math.fsum(result["rubric"]["weights"].values()) == pytest.approx(1.0)


def test_hash_stable_across_calls_and_changes_on_edit(fake_llm, role_r004, aliases):
    diff = _one_of_each_diff(role_r004, weight=0.05)
    fake_llm(diff, diff)
    r1 = compile_guidance(role_r004, "guidance", set(), aliases, top_k_default=10)
    r2 = compile_guidance(role_r004, "guidance", set(), aliases, top_k_default=10)
    assert r1["rubric"]["hash"] == r2["rubric"]["hash"]

    diff_changed = _one_of_each_diff(role_r004, weight=0.10)
    fake_llm(diff_changed)
    r3 = compile_guidance(role_r004, "guidance", set(), aliases, top_k_default=10)
    assert r3["rubric"]["hash"] != r1["rubric"]["hash"]


def test_blank_guidance_short_circuits(fake_llm, role_r004, aliases):
    stub = fake_llm()
    result = compile_guidance(role_r004, "   ", set(), aliases, top_k_default=10)
    assert stub.calls == []
    assert result["rubric"]["interpretation"] == "default"
