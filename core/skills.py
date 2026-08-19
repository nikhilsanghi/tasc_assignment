"""Skills matching: 3-tier cascade (tiers 1-2 here; tier 3 semantic added in Phase 3)."""
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


def alias_set(token: str, aliases: dict) -> set[str]:
    token = norm_token(token)
    result = {token}
    result.update(v.casefold() for v in aliases.get("expand", {}).get(token, []))
    result.update(v.casefold() for v in aliases.get("synonyms", {}).get(token, []))
    return result


def match_skill(requirement: str, cand_tokens: list[str], aliases: dict, sim: dict | None = None) -> dict | None:
    req = norm_token(requirement)
    cand_set = {norm_token(c) for c in cand_tokens}
    if req in cand_set:
        return {"skill": requirement, "tier": "exact", "evidence_token": req, "similarity": None}
    req_aliases = alias_set(req, aliases)
    for cand in cand_tokens:
        if req_aliases & alias_set(cand, aliases):
            return {"skill": requirement, "tier": "alias", "evidence_token": norm_token(cand), "similarity": None}
    return None


def overlap_count(req_tokens: list[str], cand_tokens: list[str], aliases: dict) -> int:
    return sum(1 for req in req_tokens if match_skill(req, cand_tokens, aliases) is not None)
