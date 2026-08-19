"""POST /api/export {role_id, rubric, approved_ids[], analyses, rerank, session_meta} -> markdown + audit.json."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from datetime import datetime, timezone

from core import llm
from core.auditor import build_audit, four_fifths, render_markdown
from core.policy import validate_rubric
from core.scorer import score_all, score_candidate
from api._shared import APIHandler, get_role, load_data, meta


def _shortlist_countries(approved: list[dict]) -> dict:
    counts: dict = {}
    for entry in approved:
        counts[entry["country"]] = counts.get(entry["country"], 0) + 1
    return counts


def handle(body: dict, headers: dict) -> tuple[int, dict]:
    role = get_role(body["role_id"])
    if role is None:
        return 404, {"error": "unknown_role"}
    errors = validate_rubric(body["rubric"])
    if errors:
        return 400, {"error": "invalid_rubric", "detail": errors}
    data = load_data()
    approved = [
        score_candidate(data["by_id"][cid], role, body["rubric"], data["aliases"], data["similarity"])
        for cid in body["approved_ids"] if cid in data["by_id"]
    ]
    full = score_all(data["candidates"], role, body["rubric"], data["aliases"], data["similarity"])
    ff = four_fifths(full["pool_countries"], _shortlist_countries(approved))
    date = datetime.now(timezone.utc).date().isoformat()
    markdown = render_markdown(role, body["rubric"], approved, body["analyses"], body["rerank"], ff, date)
    prompt_hashes = {"compiler": llm.prompt_hash("compiler"), "analyst": llm.prompt_hash("analyst"),
                      "reranker": llm.prompt_hash("reranker")}
    audit_json = build_audit(body, markdown, ff, data["similarity"].get("_meta", {}),
                              prompt_hashes, data["policy"]["version"])
    return 200, {"markdown": markdown, "audit_json": audit_json}


class handler(APIHandler):
    handle_fn = staticmethod(handle)
    methods = ("POST",)
