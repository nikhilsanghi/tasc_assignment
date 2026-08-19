"""POST /api/score {role_id, rubric} -> deterministic ranking, no LLM (D-02)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.policy import validate_rubric
from core.scorer import score_all
from api._shared import APIHandler, get_role, load_data, meta


def handle(body: dict, headers: dict) -> tuple[int, dict]:
    role = get_role(body["role_id"])
    if role is None:
        return 404, {"error": "unknown_role"}
    errors = validate_rubric(body["rubric"])
    if errors:
        return 400, {"error": "invalid_rubric", "detail": errors}
    data = load_data()
    result = score_all(data["candidates"], role, body["rubric"], data["aliases"], data["similarity"])
    top_k = body["rubric"]["top_k"]
    return 200, {
        "ranked": result["ranked"][:top_k], "total_ranked": len(result["ranked"]),
        "insufficient_data": result["insufficient_data"], "filtered_out": result["filtered_out"],
        "unevaluable": result["unevaluable"], "decomposition": result["decomposition"],
        "flags": result["flags"], "pool_countries": result["pool_countries"],
        "meta": meta(),
    }


class handler(APIHandler):
    handle_fn = staticmethod(handle)
    methods = ("POST",)
