import json

from core.auditor import four_fifths, render_markdown
from core.paths import DATA, ROOT
from core.policy import default_rubric
from core.scorer import score_all, score_candidate
from core.skills import load_aliases, load_similarity

ANALYSES = {
    "C101": {"analysis": {
        "candidate_id": "C101", "overlaps": [
            {"requirement": "SQL", "evidence": "SQL", "source_field": "skills", "tier": "exact"},
            {"requirement": "Python/R", "evidence": "Python", "source_field": "skills", "tier": "alias"},
        ],
        "gaps": [{"requirement": "data visualization", "severity": "required", "note": "no visualization tooling listed"}],
        "fit_brief": "Strong analyst profile with directly evidenced SQL and Python skills.",
        "clarifying_questions": [
            {"text": "Can you describe your data visualization experience?", "kind": "gap"},
            {"text": "Do you have hands-on A/B testing experience?", "kind": "gap"},
            {"text": "Profile conflict: location shows Cairo|Egypt vs Dubai|UAE - which is current?", "kind": "data"},
        ],
        "data_flags": [], "confidence": "medium",
    }, "critic": {"passed": True, "failures": [], "checks": 9}, "regenerated": False},
    "C037": {"analysis": {
        "candidate_id": "C037", "overlaps": [
            {"requirement": "SQL", "evidence": "SQL", "source_field": "skills", "tier": "exact"},
        ],
        "gaps": [{"requirement": "data visualization", "severity": "required", "note": "no visualization tooling listed"}],
        "fit_brief": "Solid SQL and Python background with five years of relevant experience.",
        "clarifying_questions": [
            {"text": "Can you describe your data visualization experience?", "kind": "gap"},
            {"text": "Have you done formal statistics coursework?", "kind": "gap"},
            {"text": "What notice period would you actually accept?", "kind": "data"},
        ],
        "data_flags": [], "confidence": "medium",
    }, "critic": {"passed": True, "failures": [], "checks": 6}, "regenerated": False},
}
RERANK_RESULT = {"disagreements": [], "llm_order": ["C101", "C037"], "missing_ids": []}


def _norm(text: str) -> str:
    return " ".join(text.split())


def test_export_matches_golden_file():
    candidates = json.loads((DATA / "candidates_normalized.json").read_text())
    roles = json.loads((DATA / "roles_normalized.json").read_text())
    role_r004 = next(r for r in roles if r["role_id"] == "R004")
    rubric = default_rubric(10)
    aliases, sim = load_aliases(), load_similarity()

    by_id = {c["candidate_id"]: c for c in candidates}
    approved = [score_candidate(by_id[cid], role_r004, rubric, aliases, sim) for cid in ("C101", "C037")]
    full = score_all(candidates, role_r004, rubric, aliases, sim)
    ff = four_fifths(full["pool_countries"], {"Egypt": 1, "Saudi Arabia": 1})

    markdown = render_markdown(role_r004, rubric, approved, ANALYSES, RERANK_RESULT, ff, date="2026-01-01")
    golden = (ROOT / "tests" / "golden" / "export_R004.md").read_text()
    assert _norm(markdown) == _norm(golden)
