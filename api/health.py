"""GET/POST /api/health - liveness check + deploy-spike proof."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import os

from core.paths import DATA, PROMPTS
from api._shared import APIHandler, load_data


def handle(body: dict, headers: dict) -> tuple[int, dict]:
    roles = [{"role_id": r["role_id"], "title": r["title"]} for r in load_data()["roles"]]
    return 200, {
        "ok": True,
        "model": os.environ.get("MODEL_REASONING", "claude-sonnet-5"),
        "data_loaded": (DATA / "open_roles.csv").exists(),
        "prompts_dir": PROMPTS.exists(),
        "roles": roles,
    }


class handler(APIHandler):
    handle_fn = staticmethod(handle)
    methods = ("GET", "POST")
