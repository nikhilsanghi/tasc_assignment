"""Reranker: single-pass listwise second opinion, advisory only, never mutates order (D-27)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pydantic import BaseModel

from core import llm
from core import policy as policy_module


class Rationale(BaseModel, extra="forbid"):
    candidate_id: str
    text: str


class RerankOutput(BaseModel, extra="forbid"):
    ranking: list[str]
    rationales: list[Rationale]


def build_prefix(role: dict, rubric: dict) -> str:
    policy = policy_module.load_policy()
    parts = [
        llm.load_prompt("reranker"),
        "",
        "## Rendered context",
        f"Policy banned criteria: {policy['banned_criteria']}",
        "",
        f"Role: {role}",
        "",
        f"Rubric interpretation: {rubric['interpretation']!r}",
        f"Rubric weights: {rubric['weights']}",
        f"Boosts: {rubric['boosts']}",
        f"Penalties: {rubric['penalties']}",
    ]
    return "\n".join(parts)


def build_user_turn(shortlist: list[dict]) -> str:
    lines = ["<shortlist>"]
    for entry in shortlist:
        lines.append(
            f"id={entry['candidate_id']} score={entry['score']} headline={entry['headline']!r} "
            f"skills={entry['skills']} exp={entry['experience_years']} seniority={entry['seniority_level']} "
            f"location={entry['location']} notice={entry['notice_days']} flags={entry['flags']}"
        )
    lines.append("</shortlist>")
    return "\n".join(lines)


def _dedupe_known(order: list[str], known_ids: set[str]) -> list[str]:
    seen, result = set(), []
    for cid in order:
        if cid in known_ids and cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result


def rerank(role: dict, rubric: dict, shortlist: list[dict]) -> dict:
    prefix = build_prefix(role, rubric)
    system_blocks = [{"type": "text", "text": prefix, "cache_control": {"type": "ephemeral"}}]
    output, usage = llm.call_structured(system_blocks, build_user_turn(shortlist), RerankOutput, stage="reranker")

    det_order = [e["candidate_id"] for e in shortlist]
    llm_order = _dedupe_known(output.ranking, set(det_order))
    missing_ids = [cid for cid in det_order if cid not in llm_order]

    det_rank = {cid: i + 1 for i, cid in enumerate(det_order)}
    llm_rank = {cid: i + 1 for i, cid in enumerate(llm_order)}
    rationale_by_id = {r.candidate_id: r.text for r in output.rationales}

    disagreements = []
    for cid in llm_order:
        delta = llm_rank[cid] - det_rank[cid]
        if abs(delta) >= 2:
            disagreements.append({
                "candidate_id": cid, "det_rank": det_rank[cid], "llm_rank": llm_rank[cid],
                "delta": delta, "rationale": rationale_by_id.get(cid, ""),
            })
    return {
        "disagreements": disagreements, "llm_order": llm_order, "missing_ids": missing_ids,
        "usage": usage, "prompt_hash": llm.prompt_hash("reranker"),
    }
