"""POST /api/analyze {role_id, candidate_id, rubric} -> evidence-cited explanation."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.analyst import analyze as analyst_analyze
from core.policy import validate_rubric
from core.scorer import score_candidate
from api._shared import APIHandler, dup_rows_for, get_role, load_data, meta


def handle(body: dict, headers: dict) -> tuple[int, dict]:
    role = get_role(body["role_id"])
    if role is None:
        return 404, {"error": "unknown_role"}
    errors = validate_rubric(body["rubric"])
    if errors:
        return 400, {"error": "invalid_rubric", "detail": errors}
    data = load_data()
    rec = data["by_id"].get(body["candidate_id"])
    if rec is None:
        return 404, {"error": "unknown_candidate"}
    scored = score_candidate(rec, role, body["rubric"], data["aliases"], data["similarity"])
    result = analyst_analyze(rec, role, body["rubric"], dup_rows_for(body["candidate_id"]), scored)
    return 200, {
        "analysis": result["analysis"], "critic": result["critic"], "regenerated": result["regenerated"],
        "meta": meta(result["usage"], result["prompt_hash"]),
    }


class handler(APIHandler):
    handle_fn = staticmethod(handle)
    methods = ("POST",)
