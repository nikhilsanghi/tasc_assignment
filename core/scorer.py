"""Deterministic scorer: the sole ranking authority (D-02). Six subscores, weighted composite."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import math

from core.skills import match_skill, match_terms
from core.scorer_filters import MENA, apply_hard_filters


def adjusted_requirements(role: dict, rubric: dict) -> dict:
    required, nice = list(role["required_skills"]), list(role["nice_to_have"])
    for override in rubric["skill_overrides"]:
        skill, to_tier = override["skill"], override["to_tier"]
        required = [s for s in required if s.casefold() != skill.casefold()]
        nice = [s for s in nice if s.casefold() != skill.casefold()]
        if to_tier == "required":
            required.append(skill)
        elif to_tier == "nice_to_have":
            nice.append(skill)
    return {"required": required, "nice": nice}


def _coverage(requirements: list[str], cand_tokens: list[str], aliases: dict, sim: dict) -> dict:
    if not requirements:
        return {"value": 1.0, "flags": [], "evidence": []}
    hits = [m for m in (match_skill(r, cand_tokens, aliases, sim) for r in requirements) if m is not None]
    return {"value": len(hits) / len(requirements), "flags": [], "evidence": hits}


def subscore_skills(rec: dict, role: dict, rubric: dict, aliases: dict, sim: dict) -> dict:
    adjusted = adjusted_requirements(role, rubric)
    if not rec["skills_norm"]:
        empty = {"value": 0.5, "flags": ["skills_missing"], "evidence": []}
        return {"required_skills": dict(empty), "nice_to_have": dict(empty)}
    return {
        "required_skills": _coverage(adjusted["required"], rec["skills_norm"], aliases, sim),
        "nice_to_have": _coverage(adjusted["nice"], rec["skills_norm"], aliases, sim),
    }


def subscore_experience(rec: dict, role: dict) -> dict:
    years = rec["experience_years"]
    if years is None:
        return {"value": 0.5, "flags": [], "evidence": None}
    if years < role["exp_min"]:
        value = 1.0 - 0.15 * (role["exp_min"] - years)
    elif years > role["exp_max"]:
        value = 1.0 - 0.05 * (years - role["exp_max"])
    else:
        value = 1.0
    return {"value": max(0.0, value), "flags": [], "evidence": years}


def subscore_seniority(rec: dict, role: dict) -> dict:
    cand_level = rec["seniority_level"]
    if cand_level is None:
        return {"value": 0.5, "flags": ["seniority_unknown"], "evidence": None}
    value = max(0.1, 1 - 0.45 * abs(cand_level - role["seniority_level"]))
    return {"value": value, "flags": [], "evidence": cand_level}


def subscore_location(rec: dict, role: dict) -> dict:
    cand_loc, role_loc = rec["location"], role["location"]
    if not cand_loc["city"] and not cand_loc["country"]:
        return {"value": 0.5, "flags": [], "evidence": cand_loc}
    if cand_loc["city"] and cand_loc["city"] == role_loc["city"]:
        value = 1.0
    elif cand_loc["country"] and cand_loc["country"] == role_loc["country"]:
        value = 0.7
    elif cand_loc["country"] in MENA:
        value = 0.4
    else:
        value = 0.2
    return {"value": value, "flags": [], "evidence": cand_loc}


_AVAILABILITY_SPECIAL = {
    "negotiable": (0.5, "notice_negotiable"), "far_future": (0.05, "notice_far_future"),
    "missing": (0.5, "notice_missing"), "unparseable": (0.5, "notice_unparseable"),
}


def subscore_availability(rec: dict) -> dict:
    kind, days = rec["notice_kind"], rec["notice_days"]
    if kind in _AVAILABILITY_SPECIAL:
        value, flag = _AVAILABILITY_SPECIAL[kind]
        return {"value": value, "flags": [flag], "evidence": kind}
    for threshold, value in ((14, 1.0), (30, 0.8), (60, 0.6), (90, 0.4)):
        if days <= threshold:
            return {"value": value, "flags": [], "evidence": days}
    return {"value": 0.2, "flags": [], "evidence": days}


def auto_questions(rec: dict, role: dict, subs: dict) -> list[str]:
    questions = []
    cand_loc, role_loc = rec["location"], role["location"]
    if cand_loc["city"] and cand_loc["city"] != role_loc["city"]:
        questions.append(f"Open to relocating to {role_loc['city']}? Currently in {cand_loc['city']}.")
    for field, values in rec.get("dup_conflicts", {}).items():
        if len(values) >= 2:
            questions.append(f"Profile conflict: {field} shows {values[0]} vs {values[1]} - which is current?")
    if rec["notice_kind"] == "negotiable":
        questions.append("What notice period would you actually accept?")
    if "experience_missing" in rec["flags"] or "experience_unparseable" in rec["flags"]:
        questions.append("Confirm total years of relevant experience.")
    return questions


def split_insufficient(recs: list[dict]) -> tuple[list[dict], list[dict]]:
    eligible, insufficient = [], []
    for rec in recs:
        (insufficient if rec["data_quality"] < 0.5 or not rec["skills"] else eligible).append(rec)
    return eligible, insufficient


def composite(subs: dict, weights: dict, boosts: list[float], penalties: list[float]) -> dict:
    weighted = math.fsum(weights[dim] * subs[dim]["value"] for dim in weights)
    total = weighted + math.fsum(boosts) - math.fsum(penalties)
    composite01 = min(1.0, max(0.0, total))
    score = round(100 * composite01)
    band = "strong" if score >= 80 else "viable-with-gaps" if score >= 60 else "stretch"
    return {"float": composite01, "score": score, "band": band}


def _fire_ops(rec: dict, ops: list[dict], aliases: dict, sim: dict) -> tuple[list[dict], list[float]]:
    fired, magnitudes = [], []
    for op in ops:
        evidence = match_terms(rec, op["fields"], op["match_terms"], aliases, sim)
        if evidence:
            fired.append({"concept": op["concept"], "evidence": evidence})
            magnitudes.append(op["magnitude"])
    return fired, magnitudes


def score_candidate(rec: dict, role: dict, rubric: dict, aliases: dict, sim: dict) -> dict:
    subs = {
        **subscore_skills(rec, role, rubric, aliases, sim),
        "experience_fit": subscore_experience(rec, role),
        "seniority": subscore_seniority(rec, role),
        "location": subscore_location(rec, role),
        "availability": subscore_availability(rec),
    }
    boosts_fired, boost_mags = _fire_ops(rec, rubric["boosts"], aliases, sim)
    penalties_fired, penalty_mags = _fire_ops(rec, rubric["penalties"], aliases, sim)
    comp = composite(subs, rubric["weights"], boost_mags, penalty_mags)
    flags = set(rec["flags"])
    for s in subs.values():
        flags.update(s["flags"])
    return {
        "candidate_id": rec["candidate_id"], "score": comp["score"], "score_float": comp["float"], "band": comp["band"],
        "subscores": subs, "boosts_fired": boosts_fired, "penalties_fired": penalties_fired,
        "flags": sorted(flags), "auto_questions": auto_questions(rec, role, subs),
        "country": rec["location"]["country"], "headline": rec["headline"], "skills": rec["skills"],
        "experience_years": rec["experience_years"], "seniority_level": rec["seniority_level"],
        "location": rec["location"], "notice_days": rec["notice_days"],
        "requirements": adjusted_requirements(role, rubric),
        "dup_group_id": rec["dup_group_id"], "dup_conflicts": rec["dup_conflicts"],
    }


def collapse_dups(scored: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    collapsed = []
    for entry in scored:
        gid = entry.get("dup_group_id")
        if gid:
            groups.setdefault(gid, []).append(entry)
        else:
            collapsed.append(entry)
    for members in groups.values():
        best = dict(max(members, key=lambda e: (e["score_float"], e["candidate_id"])))
        best["dup_members"] = sorted(m["candidate_id"] for m in members)
        collapsed.append(best)
    return collapsed


def score_all(recs: list[dict], role: dict, rubric: dict, aliases: dict, sim: dict) -> dict:
    eligible, insufficient = split_insufficient(recs)
    kept, removed, unevaluable = apply_hard_filters(eligible, rubric, role, aliases, sim)
    scored = [score_candidate(rec, role, rubric, aliases, sim) for rec in kept]
    ranked = sorted(collapse_dups(scored), key=lambda e: (-e["score_float"], e["candidate_id"]))
    pool_countries: dict[str, int] = {}
    for entry in ranked:
        pool_countries[entry["country"]] = pool_countries.get(entry["country"], 0) + 1
    return {
        "ranked": ranked,
        "insufficient_data": [r["candidate_id"] for r in insufficient],
        "filtered_out": removed,
        "unevaluable": unevaluable,
        "decomposition": {e["candidate_id"]: e for e in ranked},
        "flags": {e["candidate_id"]: e["flags"] for e in ranked},
        "pool_countries": pool_countries,
    }
