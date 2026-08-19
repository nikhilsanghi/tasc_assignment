"""POST /api/rerank {role_id, top_ids[], rubric} -> advisory second opinion (D-27)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.policy import validate_rubric
from core.reranker import rerank as reranker_rerank
from core.scorer import score_candidate
from api._shared import APIHandler, get_role, load_data, meta


def handle(body: dict, headers: dict) -> tuple[int, dict]:
    role = get_role(body["role_id"])
    if role is None:
        return 404, {"error": "unknown_role"}
    errors = validate_rubric(body["rubric"])
    if errors:
        return 400, {"error": "invalid_rubric", "detail": errors}
    data = load_data()
    shortlist = [
        score_candidate(data["by_id"][cid], role, body["rubric"], data["aliases"], data["similarity"])
        for cid in body["top_ids"] if cid in data["by_id"]
    ]
    result = reranker_rerank(role, body["rubric"], shortlist)
    return 200, {
        "disagreements": result["disagreements"], "llm_order": result["llm_order"],
        "missing_ids": result["missing_ids"], "meta": meta(result["usage"], result["prompt_hash"]),
    }


class handler(APIHandler):
    handle_fn = staticmethod(handle)
    methods = ("POST",)
