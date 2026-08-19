import pytest

from api import analyze, compile_rubric, export, rerank, score
from api._shared import dispatch
from core.analyst import AnalystOutput
from core.policy import default_rubric
from core.reranker import RerankOutput

ENDPOINTS = [
    (compile_rubric.handle, {"role_id": "R004", "guidance": ""}),
    (score.handle, {"role_id": "R004", "rubric": None}),
    (analyze.handle, {"role_id": "R004", "candidate_id": "C101", "rubric": None}),
    (rerank.handle, {"role_id": "R004", "top_ids": [], "rubric": None}),
    (export.handle, {"role_id": "R004", "rubric": None, "approved_ids": [], "analyses": {}, "rerank": {}}),
]


@pytest.mark.parametrize("handle, body", ENDPOINTS)
def test_401_without_access_code(handle, body, default_rubric):
    body = dict(body)
    if "rubric" in body:
        body["rubric"] = default_rubric
    status, payload = dispatch(handle, {}, body)
    assert status == 401
    assert payload == {"error": "unauthorized"}


def test_400_bad_rubric_weight(headers_ok, default_rubric):
    bad = dict(default_rubric)
    bad["weights"] = dict(default_rubric["weights"])
    bad["weights"]["required_skills"] = 0.9
    status, payload = dispatch(score.handle, headers_ok, {"role_id": "R004", "rubric": bad})
    assert status == 400
    assert payload["error"] == "invalid_rubric"


def test_compile_rubric_blank_guidance_default(headers_ok):
    status, payload = dispatch(compile_rubric.handle, headers_ok, {"role_id": "R004", "guidance": ""})
    assert status == 200
    assert payload["rubric"]["interpretation"] == "default"


def test_score_r004_shape(headers_ok, default_rubric):
    status, payload = dispatch(score.handle, headers_ok, {"role_id": "R004", "rubric": default_rubric})
    assert status == 200
    assert len(payload["ranked"]) == 10
    assert payload["total_ranked"] > 10
    assert set(payload["insufficient_data"]) == {"C118", "C112"}


def test_score_unknown_role_404(headers_ok, default_rubric):
    status, payload = dispatch(score.handle, headers_ok, {"role_id": "R999", "rubric": default_rubric})
    assert status == 404


def test_analyze_shape(headers_ok, default_rubric, monkeypatch):
    out = AnalystOutput(
        candidate_id="C101", overlaps=[{"requirement": "SQL", "evidence": "SQL", "source_field": "skills", "tier": "exact"}],
        gaps=[], fit_brief="Solid candidate with relevant background overall.",
        clarifying_questions=[{"text": "q1", "kind": "gap"}, {"text": "q2", "kind": "gap"}, {"text": "q3", "kind": "data"}],
        data_flags=[], confidence="high",
    )
    usage = {"input_tokens": 10, "output_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    monkeypatch.setattr("core.llm.call_structured", lambda *a, **kw: (out, usage))
    status, payload = dispatch(analyze.handle, headers_ok, {"role_id": "R004", "candidate_id": "C101", "rubric": default_rubric})
    assert status == 200
    assert "analysis" in payload and "critic" in payload and "regenerated" in payload


def test_rerank_shape(headers_ok, default_rubric, monkeypatch):
    out = RerankOutput(ranking=["C101", "C037"], rationales=[{"candidate_id": "C101", "text": "r"}])
    usage = {"input_tokens": 10, "output_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    monkeypatch.setattr("core.llm.call_structured", lambda *a, **kw: (out, usage))
    status, payload = dispatch(rerank.handle, headers_ok, {"role_id": "R004", "top_ids": ["C101", "C037"], "rubric": default_rubric})
    assert status == 200
    assert "disagreements" in payload and "llm_order" in payload and "missing_ids" in payload


def test_export_shape(headers_ok, default_rubric):
    analysis = {
        "candidate_id": "C101", "overlaps": [], "gaps": [], "fit_brief": "Fine.",
        "clarifying_questions": [{"text": "q1", "kind": "gap"}, {"text": "q2", "kind": "gap"}, {"text": "q3", "kind": "data"}],
        "data_flags": [], "confidence": "medium",
    }
    body = {
        "role_id": "R004", "rubric": default_rubric, "approved_ids": ["C101"],
        "analyses": {"C101": {"analysis": analysis, "critic": {"passed": True, "failures": [], "checks": 3}, "regenerated": False}},
        "rerank": {"disagreements": [], "llm_order": ["C101"], "missing_ids": []},
        "session_meta": {"guidance": "", "rejected": [], "adjustments": [], "decomposition": {}, "compiled_at": "x", "approved_at": "y"},
    }
    status, payload = dispatch(export.handle, headers_ok, body)
    assert status == 200
    assert "markdown" in payload
    audit_keys = {
        "role_id", "guidance", "rubric", "rejected", "adjustments", "decomposition", "approved_ids",
        "analyses", "rerank", "four_fifths", "markdown", "compiled_at", "approved_at", "generated_at",
        "model_ids", "prompt_hashes", "policy_version", "similarity_cache",
    }
    assert audit_keys <= set(payload["audit_json"].keys())
