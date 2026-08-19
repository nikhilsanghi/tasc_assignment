from core.reranker import RerankOutput, rerank


def _shortlist(ids):
    return [
        {"candidate_id": cid, "score": 90 - i, "headline": "h", "skills": [], "experience_years": 3,
         "seniority_level": 1.0, "location": {"city": "Dubai", "country": "UAE"}, "notice_days": 0, "flags": []}
        for i, cid in enumerate(ids)
    ]


def _output(ranking, rationale_ids=None):
    rationale_ids = rationale_ids or ranking
    return RerankOutput(ranking=ranking, rationales=[{"candidate_id": cid, "text": "r"} for cid in rationale_ids])


def test_never_mutates_deterministic_order(fake_llm, role_r004, default_rubric):
    shortlist = _shortlist(["C1", "C2", "C3", "C4"])
    fake_llm(_output(["C4", "C1", "C2", "C3"]))
    result = rerank(role_r004, default_rubric, shortlist)
    assert [e["candidate_id"] for e in shortlist] == ["C1", "C2", "C3", "C4"]
    assert "det_order" not in result


def test_only_large_deltas_emitted(fake_llm, role_r004, default_rubric):
    shortlist = _shortlist(["C1", "C2", "C3", "C4"])
    fake_llm(_output(["C2", "C1", "C4", "C3"]))
    result = rerank(role_r004, default_rubric, shortlist)
    deltas = {d["candidate_id"]: d["delta"] for d in result["disagreements"]}
    assert deltas == {}


def test_large_delta_flagged(fake_llm, role_r004, default_rubric):
    shortlist = _shortlist(["C1", "C2", "C3", "C4"])
    fake_llm(_output(["C4", "C2", "C3", "C1"]))
    result = rerank(role_r004, default_rubric, shortlist)
    ids = {d["candidate_id"] for d in result["disagreements"]}
    assert "C4" in ids
    assert "C1" in ids
    for d in result["disagreements"]:
        assert abs(d["delta"]) >= 2


def test_unknown_ids_ignored(fake_llm, role_r004, default_rubric):
    shortlist = _shortlist(["C1", "C2"])
    fake_llm(_output(["C1", "C99", "C2"]))
    result = rerank(role_r004, default_rubric, shortlist)
    assert "C99" not in result["llm_order"]
    assert result["llm_order"] == ["C1", "C2"]


def test_omitted_ids_become_missing(fake_llm, role_r004, default_rubric):
    shortlist = _shortlist(["C1", "C2", "C3"])
    fake_llm(_output(["C1", "C2"]))
    result = rerank(role_r004, default_rubric, shortlist)
    assert result["missing_ids"] == ["C3"]


def test_duplicate_ids_first_wins(fake_llm, role_r004, default_rubric):
    shortlist = _shortlist(["C1", "C2"])
    fake_llm(_output(["C1", "C2", "C1"]))
    result = rerank(role_r004, default_rubric, shortlist)
    assert result["llm_order"] == ["C1", "C2"]
