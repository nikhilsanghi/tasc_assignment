import math
import random

import pytest

from core.policy import DEFAULT_WEIGHTS, apply_ops, default_rubric, validate_ops, validate_rubric


def _vocab():
    return {"python", "sql", "docker"}


def test_guard_accepts_one_valid_instance_of_each_op(role_r004, aliases):
    role_skill = role_r004["required_skills"][0]
    ops = [
        {"op": "reweight", "dimension": "availability", "new_weight": 0.25},
        {"op": "promote_demote_skill", "skill": role_skill, "to_tier": "required"},
        {"op": "hard_filter", "field": "notice_days_max", "value": 30},
        {"op": "boost_penalty", "concept": "x", "fields": ["skills"], "match_terms": ["python"],
         "direction": "boost", "magnitude": 0.05},
        {"op": "set_top_k", "value": 15},
    ]
    accepted, rejected = validate_ops(ops, role_r004, _vocab(), aliases)
    assert rejected == []
    assert len(accepted) == 5


def test_default_rubric_has_hash_and_interpretation():
    rubric = default_rubric(10)
    assert rubric["interpretation"] == "default"
    assert isinstance(rubric["hash"], str) and len(rubric["hash"]) == 12


def test_two_reweights_applied_as_one_batch():
    ops = [
        {"op": "reweight", "dimension": "required_skills", "new_weight": 0.5},
        {"op": "reweight", "dimension": "nice_to_have", "new_weight": 0.3},
    ]
    rubric, _ = apply_ops(DEFAULT_WEIGHTS, ops, 10, "test")
    pre_renorm_sum = 0.5 + 0.3 + DEFAULT_WEIGHTS["experience_fit"] + DEFAULT_WEIGHTS["seniority"] + \
        DEFAULT_WEIGHTS["location"] + DEFAULT_WEIGHTS["availability"]
    assert rubric["weights"]["required_skills"] == pytest.approx(0.5 / pre_renorm_sum)
    assert math.fsum(rubric["weights"].values()) == pytest.approx(1.0)


REJECTION_TABLE = [
    ({"op": "reweight", "dimension": "required_skills", "new_weight": 0.9}, "weight_bounds"),
    ({"op": "hard_filter", "field": "location_scope", "value": "exclude_egypt"}, "location_scope_values"),
    ({"op": "hard_filter", "field": "country", "value": "Egypt"}, "hard_filter_allowed_fields"),
    ({"op": "boost_penalty", "concept": "x", "fields": ["skills"], "match_terms": ["emirati"],
      "direction": "boost", "magnitude": 0.05}, "banned_terms"),
    ({"op": "boost_penalty", "concept": "x", "fields": ["candidate_id"], "match_terms": ["python"],
      "direction": "boost", "magnitude": 0.05}, "boost_allowed_fields"),
    ({"op": "boost_penalty", "concept": "x", "fields": ["skills"], "match_terms": ["python"],
      "direction": "boost", "magnitude": 0.5}, "boost_magnitude_bounds"),
    ({"op": "set_top_k", "value": 100}, "top_k_bounds"),
    ({"op": "nonexistent_op"}, "allowed_operations"),
]


@pytest.mark.parametrize("op, detail", REJECTION_TABLE)
def test_guard_rejects_banned_ops(op, detail, role_r004, aliases):
    accepted, rejected = validate_ops([op], role_r004, _vocab(), aliases)
    assert accepted == []
    assert rejected[0]["reason"] == "policy_violation"
    assert rejected[0]["detail"] == detail


def test_post_renorm_clamp():
    weights = {"availability": 0.60, "required_skills": 0.0, "nice_to_have": 0.0,
               "experience_fit": 0.0, "seniority": 0.0, "location": 0.05}
    rubric, adjustments = apply_ops(weights, [], 10, "test")
    assert rubric["weights"]["availability"] == pytest.approx(0.60)
    assert adjustments != []
    assert math.fsum(rubric["weights"].values()) == pytest.approx(1.0)


def test_weight_invariant_property():
    rng = random.Random(7)
    dims = list(DEFAULT_WEIGHTS)
    for _ in range(50):
        ops = [{"op": "reweight", "dimension": rng.choice(dims), "new_weight": rng.uniform(0.0, 0.60)}
               for _ in range(rng.randint(1, 3))]
        rubric, _ = apply_ops(DEFAULT_WEIGHTS, ops, 10, "test")
        assert math.fsum(rubric["weights"].values()) == pytest.approx(1.0, abs=1e-6)
        assert all(v <= 0.60 + 1e-9 for v in rubric["weights"].values())


def test_validate_rubric():
    assert validate_rubric(default_rubric(10)) == []

    bad_weight = default_rubric(10)
    bad_weight["weights"]["required_skills"] = 0.9
    assert validate_rubric(bad_weight) != []

    banned = default_rubric(10)
    banned["boosts"] = [{"concept": "x", "fields": ["skills"], "match_terms": ["emirati"], "magnitude": 0.05}]
    assert validate_rubric(banned) != []

    tampered = default_rubric(10)
    tampered["hash"] = "deadbeefdead"
    assert validate_rubric(tampered) != []
