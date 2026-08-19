import random

import pytest

from core.policy import DEFAULT_WEIGHTS, default_rubric
from core.scorer import collapse_dups, composite, score_all, score_candidate, split_insufficient
from core.scorer_filters import apply_hard_filters

GOLDEN_SUBS = {
    "required_skills": {"value": 0.75}, "nice_to_have": {"value": 0.5}, "experience_fit": {"value": 1.0},
    "seniority": {"value": 1.0}, "location": {"value": 0.5}, "availability": {"value": 1.0},
}


def test_golden_worked_example():
    result = composite(GOLDEN_SUBS, DEFAULT_WEIGHTS, [], [])
    assert result["float"] == pytest.approx(0.8125, abs=1e-9)
    assert result["score"] == 81


def test_golden_boost():
    result = composite(GOLDEN_SUBS, DEFAULT_WEIGHTS, [0.05], [])
    assert result["score"] == 86


def test_golden_penalty():
    result = composite(GOLDEN_SUBS, DEFAULT_WEIGHTS, [], [0.10])
    assert result["score"] == 71


def test_c101_real_candidate_decomposition(candidates, role_r004, aliases, similarity):
    c101 = next(c for c in candidates if c["candidate_id"] == "C101")
    rubric = default_rubric(10)
    entry = score_candidate(c101, role_r004, rubric, aliases, similarity)
    subs = entry["subscores"]
    assert subs["required_skills"]["value"] == pytest.approx(0.75)
    assert subs["nice_to_have"]["value"] == pytest.approx(1.0)
    assert subs["experience_fit"]["value"] == pytest.approx(1.0)
    assert subs["seniority"]["value"] == pytest.approx(1.0)
    assert subs["location"]["value"] == pytest.approx(0.4)
    assert subs["availability"]["value"] == pytest.approx(0.8)
    assert entry["score"] == 82


def test_order_invariance(candidates, role_r004, aliases, similarity):
    rubric = default_rubric(10)
    base_ids = None
    for seed in (1, 2, 3):
        shuffled = list(candidates)
        random.Random(seed).shuffle(shuffled)
        result = score_all(shuffled, role_r004, rubric, aliases, similarity)
        ids = [e["candidate_id"] for e in result["ranked"]]
        if base_ids is None:
            base_ids = ids
        else:
            assert ids == base_ids


def test_availability_table():
    from core.scorer import subscore_availability

    table = [
        ("ok", 0, 1.0), ("ok", 14, 1.0), ("ok", 30, 0.8), ("ok", 45, 0.6), ("ok", 60, 0.6),
        ("ok", 90, 0.4), ("ok", 91, 0.2), ("negotiable", None, 0.5), ("far_future", None, 0.05),
        ("missing", None, 0.5), ("unparseable", None, 0.5),
    ]
    for kind, days, expected in table:
        rec = {"notice_kind": kind, "notice_days": days}
        assert subscore_availability(rec)["value"] == pytest.approx(expected)


def test_hard_filter_notice_days_max(candidates, role_r004, aliases, similarity):
    eligible, _ = split_insufficient(candidates)
    rubric = default_rubric(10)
    rubric["hard_filters"] = [{"field": "notice_days_max", "value": 30}]
    kept, removed, unevaluable = apply_hard_filters(eligible, rubric, role_r004, aliases, similarity)
    assert removed != []
    assert all(c["notice_days"] is None or c["notice_days"] <= 30 or
               c["candidate_id"] in unevaluable for c in kept)
    negotiable_kept = [c for c in kept if c["notice_kind"] == "negotiable"]
    assert negotiable_kept
    assert all(unevaluable[c["candidate_id"]] == ["filter_unevaluable_notice_days_max"] for c in negotiable_kept)


def test_hard_filter_location_scope_role_city(candidates, role_r004, aliases, similarity):
    eligible, _ = split_insufficient(candidates)
    rubric = default_rubric(10)
    rubric["hard_filters"] = [{"field": "location_scope", "value": "role_city"}]
    kept, removed, unevaluable = apply_hard_filters(eligible, rubric, role_r004, aliases, similarity)
    assert removed != []
    assert all(c["location"]["city"] == "Dubai" for c in kept if c["candidate_id"] not in unevaluable)


def test_hard_filter_must_have_skill(candidates, role_r004, aliases, similarity):
    from core.skills import match_skill

    eligible, _ = split_insufficient(candidates)
    rubric = default_rubric(10)
    rubric["hard_filters"] = [{"field": "must_have_skill", "value": "python"}]
    kept, removed, _ = apply_hard_filters(eligible, rubric, role_r004, aliases, similarity)
    assert removed != []
    assert all(match_skill("python", c["skills_norm"], aliases, similarity) is not None for c in kept)


def test_dup_collapse_c014(candidates, role_r004, aliases, similarity):
    rubric = default_rubric(10)
    scored = [score_candidate(c, role_r004, rubric, aliases, similarity) for c in candidates if c["skills"]]
    collapsed = collapse_dups(scored)
    c014_group_id = next(e["dup_group_id"] for e in scored if e["candidate_id"] == "C014")
    matches = [e for e in collapsed if e["candidate_id"] == "C014" or "C014" in e.get("dup_members", [])]
    assert len(matches) == 1
    assert set(matches[0]["dup_members"]) >= {"C014", "C106"}
    assert all(e["dup_group_id"] != c014_group_id for e in collapsed if e is not matches[0])


def test_insufficient_strip(candidates):
    eligible, insufficient = split_insufficient(candidates)
    assert {c["candidate_id"] for c in insufficient} == {"C118", "C112"}
    assert len(eligible) == len(candidates) - 2


def test_boost_fires_once_and_stacks_and_clips(role_r004, aliases, similarity):
    rec = {
        "candidate_id": "TEST1", "skills": ["SQL", "Python", "Tableau", "Statistics", "A/B testing"],
        "skills_norm": ["sql", "python", "data visualization", "statistics", "a/b testing experience"],
        "experience_years": 3.0, "seniority_level": 1.0, "location": {"city": "Dubai", "country": "UAE"},
        "notice_days": 0, "notice_kind": "ok", "flags": [], "dup_group_id": None, "dup_conflicts": {},
        "headline": "python engineer python python", "data_quality": 1.0,
        "normalized_text": {"headline": "python engineer python python"},
    }
    rubric = default_rubric(10)
    rubric["boosts"] = [
        {"concept": "py", "fields": ["headline"], "match_terms": ["python", "engineer", "nomatch"], "magnitude": 0.10},
        {"concept": "py2", "fields": ["headline"], "match_terms": ["python"], "magnitude": 0.10},
    ]
    entry = score_candidate(rec, role_r004, rubric, aliases, similarity)
    assert len(entry["boosts_fired"]) == 2
    weighted_only = composite(entry["subscores"], rubric["weights"], [], [])
    assert weighted_only["float"] > 0.9
    assert entry["score_float"] == pytest.approx(1.0)
    assert entry["score"] == 100
