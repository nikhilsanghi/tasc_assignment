"""Live end-to-end drive through dispatch: compile -> score -> analyze -> rerank -> export."""
import pytest

from api import analyze, compile_rubric, export, rerank, score
from api._shared import dispatch
from core.paths import ROOT

pytestmark = pytest.mark.live

GUIDANCE = "prioritize immediate availability; A/B testing matters a lot"


def test_e2e_live(headers_ok):
    status, compiled = dispatch(compile_rubric.handle, headers_ok, {"role_id": "R004", "guidance": GUIDANCE})
    assert status == 200 and "rubric" in compiled
    rubric = compiled["rubric"]

    status, scored = dispatch(score.handle, headers_ok, {"role_id": "R004", "rubric": rubric})
    assert status == 200 and len(scored["ranked"]) == rubric["top_k"]

    top3 = scored["ranked"][:3]
    analyses = {}
    for entry in top3:
        status, result = dispatch(analyze.handle, headers_ok, {
            "role_id": "R004", "candidate_id": entry["candidate_id"], "rubric": rubric,
        })
        assert status == 200 and "analysis" in result and "critic" in result
        analyses[entry["candidate_id"]] = result

    status, rerank_result = dispatch(rerank.handle, headers_ok, {
        "role_id": "R004", "top_ids": [e["candidate_id"] for e in top3], "rubric": rubric,
    })
    assert status == 200 and "llm_order" in rerank_result

    export_body = {
        "role_id": "R004", "rubric": rubric, "approved_ids": [e["candidate_id"] for e in top3],
        "analyses": analyses, "rerank": rerank_result,
        "session_meta": {
            "guidance": GUIDANCE, "rejected": compiled["rejected"], "adjustments": compiled["adjustments"],
            "decomposition": scored["decomposition"], "compiled_at": "test", "approved_at": "test",
        },
    }
    status, exported = dispatch(export.handle, headers_ok, export_body)
    assert status == 200 and "markdown" in exported and "audit_json" in exported

    (ROOT / "tests" / "golden" / "export_R004_live.md").write_text(exported["markdown"])
