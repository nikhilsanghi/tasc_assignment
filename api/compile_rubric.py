"""POST /api/compile_rubric {role_id, guidance} -> compiled rubric + echo-back."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import os

from core import rubric as rubric_module
from api._shared import APIHandler, get_role, load_data, meta


def handle(body: dict, headers: dict) -> tuple[int, dict]:
    role = get_role(body["role_id"])
    if role is None:
        return 404, {"error": "unknown_role"}
    data = load_data()
    top_k_default = int(os.environ.get("TOP_K", 10))
    result = rubric_module.compile_guidance(role, body.get("guidance", ""), data["vocab"], data["aliases"], top_k_default)
    return 200, {
        "rubric": result["rubric"], "interpretation": result["rubric"]["interpretation"],
        "ops_accepted": result["ops_accepted"], "rejected": result["rejected"], "adjustments": result["adjustments"],
        "meta": meta(result["usage"], result["prompt_hash"]),
    }


class handler(APIHandler):
    handle_fn = staticmethod(handle)
    methods = ("POST",)
