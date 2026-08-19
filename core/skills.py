"""Skills matching: 3-tier cascade (exact, alias, semantic)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import functools
import json

from core.paths import DATA


def norm_token(s: str) -> str:
    return s.strip().casefold()


@functools.lru_cache
def load_aliases() -> dict:
    return json.loads((DATA / "skill_aliases.json").read_text())


@functools.lru_cache
def load_similarity() -> dict:
    return json.loads((DATA / "skill_similarity.json").read_text())


def alias_set(token: str, aliases: dict) -> set[str]:
    token = norm_token(token)
    result = {token}
    result.update(v.casefold() for v in aliases.get("expand", {}).get(token, []))
    result.update(v.casefold() for v in aliases.get("synonyms", {}).get(token, []))
    return result


def _semantic_match(req: str, cand_tokens: list[str], aliases: dict, sim: dict) -> dict | None:
    atoms = {req} | {a.casefold() for a in aliases.get("expand", {}).get(req, [])}
    table = sim.get("similarity", {})
    best_score, best_cand = 0.0, None
    for atom in atoms:
        row = table.get(atom, {})
        for cand in cand_tokens:
            score = row.get(norm_token(cand))
            if score is not None and score > best_score:
                best_score, best_cand = score, norm_token(cand)
    if best_cand is not None and best_score >= 0.75:
        return {"skill": req, "tier": "semantic", "evidence_token": best_cand, "similarity": best_score}
    return None


def match_skill(requirement: str, cand_tokens: list[str], aliases: dict, sim: dict | None = None) -> dict | None:
    req = norm_token(requirement)
    cand_set = {norm_token(c) for c in cand_tokens}
    if req in cand_set:
        return {"skill": requirement, "tier": "exact", "evidence_token": req, "similarity": None}
    req_aliases = alias_set(req, aliases)
    for cand in cand_tokens:
        if req_aliases & alias_set(cand, aliases):
            return {"skill": requirement, "tier": "alias", "evidence_token": norm_token(cand), "similarity": None}
    if sim is not None:
        return _semantic_match(req, cand_tokens, aliases, sim)
    return None


def overlap_count(req_tokens: list[str], cand_tokens: list[str], aliases: dict) -> int:
    return sum(1 for req in req_tokens if match_skill(req, cand_tokens, aliases) is not None)


def _snippet(text: str, term: str, width: int = 60) -> str:
    idx = text.find(term)
    if idx == -1:
        return ""
    start, end = max(0, idx - width // 2), min(len(text), idx + len(term) + width // 2)
    return text[start:end]


def match_terms(rec: dict, fields: list[str], terms: list[str], aliases: dict, sim: dict | None) -> list[dict]:
    evidence = []
    for field in fields:
        for term in terms:
            if field == "skills":
                if match_skill(term, rec["skills_norm"], aliases, sim) is not None:
                    evidence.append({"field": field, "term": term, "snippet": term})
                continue
            text = rec.get("normalized_text", {}).get(field, "")
            needle = norm_token(term)
            if needle in text:
                evidence.append({"field": field, "term": term, "snippet": _snippet(text, needle)})
    return evidence
