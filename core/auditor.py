"""Auditor: four-fifths demonstration, hiring-manager Markdown export (D-34), audit bundle."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from datetime import datetime, timezone

from core import llm

FOUR_FIFTHS_NOTE = "DEMONSTRATION on a location proxy; production runs this on lawfully collected demographic data."


def four_fifths(pool_countries: dict, shortlist_countries: dict) -> dict:
    rates = {c: (shortlist_countries.get(c, 0) / n if n else 0.0) for c, n in pool_countries.items()}
    max_rate = max(rates.values()) if rates else 0.0
    ratios = {c: (r / max_rate if max_rate else 0.0) for c, r in rates.items()}
    flagged = [c for c, r in ratios.items() if r < 0.8]
    return {"rates": rates, "ratios": ratios, "flagged": flagged, "note": FOUR_FIFTHS_NOTE}


def _first_sentence(text: str) -> str:
    return text.split(". ")[0].rstrip(".") + "."


def _summary_table(approved: list[dict], analyses: dict) -> list[str]:
    lines = ["## Summary table", "| # | Candidate | Score | Band | Key overlaps | Key gaps | Availability |",
              "|---|---|---|---|---|---|---|"]
    for i, entry in enumerate(approved, 1):
        analysis = analyses[entry["candidate_id"]]["analysis"]
        overlaps = ", ".join(o["requirement"] for o in analysis["overlaps"][:3])
        gaps = ", ".join(g["requirement"] for g in analysis["gaps"][:3])
        avail = "immediate" if entry["notice_days"] == 0 else f"{entry['notice_days']}d"
        lines.append(f"| {i} | {entry['candidate_id']} | {entry['score']} | {entry['band']} | {overlaps} | {gaps} | {avail} |")
    return lines


def _candidate_section(entry: dict, analysis_result: dict, rerank_result: dict) -> list[str]:
    cid, analysis = entry["candidate_id"], analysis_result["analysis"]
    overlaps = " ".join(f'{o["requirement"]} — "{o["evidence"]}" ({o["source_field"]})' for o in analysis["overlaps"])
    gaps = " ".join(f'{g["requirement"]} ({g["severity"]}) — {g["note"]}' for g in analysis["gaps"])
    questions = " ".join(f"{i}. {q['text']}" for i, q in enumerate(analysis["clarifying_questions"], 1))
    flags = ", ".join(analysis["data_flags"]) or "none"
    disagreement = next((d for d in rerank_result.get("disagreements", []) if d["candidate_id"] == cid), None)
    rr_view = f"flagged: {disagreement['rationale']}" if disagreement else "agrees"
    return [
        f"## {cid} — {entry['headline']}   Score {entry['score']} · {entry['band']}",
        f"**Why this candidate:** {analysis['fit_brief']}",
        f"**Overlaps:** {overlaps}",
        f"**Gaps:** {gaps}",
        f"**Questions to ask:** {questions}",
        f"**Flags:** {flags} · Reranker view: {rr_view}",
        "",
    ]


def _four_fifths_one_liner(ff: dict) -> str:
    if not ff["flagged"]:
        return "no countries flagged below the four-fifths threshold"
    return f"flagged countries below four-fifths: {', '.join(ff['flagged'])}"


def render_markdown(role: dict, rubric: dict, approved: list[dict], analyses: dict,
                     rerank_result: dict, ff: dict, date: str) -> str:
    lines = [
        f"# Shortlist — {role['title']} ({role['role_id']})",
        f"Prepared {date} · {len(approved)} candidates approved by the recruiter · rubric: {_first_sentence(rubric['interpretation'])}",
        "",
    ]
    lines += _summary_table(approved, analyses)
    lines.append("")
    for entry in approved:
        lines += _candidate_section(entry, analyses[entry["candidate_id"]], rerank_result)
    lines += [
        "## Notes",
        f"- Scores are deterministic (rubric v{rubric['hash']}); LLM text is evidence-cited and critic-verified.",
        f"- Adverse-impact check (demonstration on a location proxy, not a protected attribute): {_four_fifths_one_liner(ff)}.",
    ]
    return "\n".join(lines)


def build_audit(body: dict, markdown: str, ff: dict, similarity_meta: dict,
                 prompt_hashes: dict, policy_version: int) -> dict:
    session_meta = body.get("session_meta", {})
    return {
        "role_id": body["role_id"],
        "guidance": session_meta.get("guidance"),
        "rubric": body["rubric"],
        "rejected": session_meta.get("rejected", []),
        "adjustments": session_meta.get("adjustments", []),
        "decomposition": session_meta.get("decomposition", {}),
        "approved_ids": body["approved_ids"],
        "analyses": body["analyses"],
        "rerank": body["rerank"],
        "four_fifths": ff,
        "markdown": markdown,
        "compiled_at": session_meta.get("compiled_at"),
        "approved_at": session_meta.get("approved_at"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_ids": {"reasoning": llm.MODEL_REASONING, "fast": llm.MODEL_FAST},
        "prompt_hashes": prompt_hashes,
        "policy_version": policy_version,
        "similarity_cache": similarity_meta,
    }
