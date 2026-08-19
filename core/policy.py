"""Policy Guard: loads immutable policy.json, validates + applies rubric-diff ops (D-19)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import functools
import hashlib
import json
import math
import re

from core.paths import DATA

SIX_DIMENSIONS = {"required_skills", "nice_to_have", "experience_fit", "seniority", "location", "availability"}
DEFAULT_WEIGHTS = {
    "required_skills": 0.35, "nice_to_have": 0.10, "experience_fit": 0.20,
    "seniority": 0.10, "location": 0.10, "availability": 0.15,
}
RUBRIC_KEYS = {"weights", "hard_filters", "skill_overrides", "boosts", "penalties", "top_k", "interpretation", "hash"}


@functools.lru_cache
def load_policy() -> dict:
    return json.loads((DATA / "policy.json").read_text())


def canonical(rubric: dict) -> dict:
    canon = {k: v for k, v in rubric.items() if k not in ("hash", "interpretation")}
    canon["weights"] = {k: round(float(v), 10) for k, v in canon["weights"].items()}
    for key in ("boosts", "penalties"):
        canon[key] = [{**e, "magnitude": round(float(e["magnitude"]), 10)} for e in canon[key]]
    return canon


def rubric_hash(rubric: dict) -> str:
    digest = hashlib.sha256(json.dumps(canonical(rubric), sort_keys=True).encode()).hexdigest()
    return digest[:12]


def default_rubric(top_k: int) -> dict:
    rubric = {
        "weights": dict(DEFAULT_WEIGHTS), "hard_filters": [], "skill_overrides": [],
        "boosts": [], "penalties": [], "top_k": top_k, "interpretation": "default",
    }
    rubric["hash"] = rubric_hash(rubric)
    return rubric


def renormalize_and_clamp(weights: dict, max_w: float) -> tuple[dict, list[dict]]:
    total = math.fsum(weights.values())
    weights = {k: v / total for k, v in weights.items()} if total else dict(weights)
    adjustments = []
    while True:
        over = [k for k, v in weights.items() if v > max_w]
        if not over:
            return weights, adjustments
        dim = over[0]
        adjustments.append({"dimension": dim, "requested": weights[dim], "applied": max_w, "reason": "weight_bounds"})
        excess = weights[dim] - max_w
        weights[dim] = max_w
        _redistribute(weights, dim, excess)


def _redistribute(weights: dict, exclude: str, excess: float) -> None:
    others = [k for k in weights if k != exclude]
    others_total = math.fsum(weights[k] for k in others)
    if others_total > 0:
        for k in others:
            weights[k] += excess * (weights[k] / others_total)
    else:
        for k in others:
            weights[k] += excess / len(others)


def _reject(op: dict, detail: str) -> dict:
    return {"text": json.dumps(op, sort_keys=True), "reason": "policy_violation", "detail": detail, "closest_supported": None}


def _validate_reweight(op: dict, policy: dict) -> dict | None:
    bounds = policy["weight_bounds"]
    w = op.get("new_weight")
    if op.get("dimension") not in SIX_DIMENSIONS or not isinstance(w, (int, float)) or not (bounds["min"] <= w <= bounds["max"]):
        return _reject(op, "weight_bounds")
    return None


def _promote_vocab(role: dict, vocab: set[str], aliases: dict) -> set[str]:
    tokens = {k.casefold() for k in aliases.get("expand", {})} | {k.casefold() for k in aliases.get("synonyms", {})}
    for values in list(aliases.get("expand", {}).values()) + list(aliases.get("synonyms", {}).values()):
        tokens |= {v.casefold() for v in values}
    role_skills = {s.casefold() for s in role["required_skills"] + role["nice_to_have"]}
    return role_skills | vocab | tokens


def _validate_promote(op: dict, role: dict, vocab: set[str], aliases: dict) -> dict | None:
    skill = (op.get("skill") or "").casefold()
    known = _promote_vocab(role, vocab, aliases)
    if skill not in known or op.get("to_tier") not in ("required", "nice_to_have", "ignore"):
        return _reject(op, "allowed_operations")
    return None


def _validate_hard_filter(op: dict, policy: dict) -> dict | None:
    field = op.get("field")
    if field not in policy["hard_filter_allowed_fields"]:
        return _reject(op, "hard_filter_allowed_fields")
    if field == "location_scope":
        return None if op.get("value") in policy["location_scope_values"] else _reject(op, "location_scope_values")
    value = op.get("value")
    if field == "notice_days_max" and not (isinstance(value, (int, float)) and 0 <= value <= 365):
        return _reject(op, "hard_filter_allowed_fields")
    if field in ("experience_years_min", "experience_years_max") and not (isinstance(value, (int, float)) and 0 <= value <= 50):
        return _reject(op, "hard_filter_allowed_fields")
    if field == "must_have_skill" and not (isinstance(value, str) and value.strip()):
        return _reject(op, "hard_filter_allowed_fields")
    return None


def _validate_boost_penalty(op: dict, policy: dict) -> dict | None:
    fields = op.get("fields") or []
    if not fields or not set(fields).issubset(set(policy["boost_allowed_fields"])):
        return _reject(op, "boost_allowed_fields")
    terms = op.get("match_terms") or []
    if not (1 <= len(terms) <= policy["boost_max_terms"]):
        return _reject(op, "boost_max_terms")
    for term in terms:
        t = (term or "").strip()
        if not t or len(t) > 40:
            return _reject(op, "boost_max_terms")
        if any(re.search(rf"\b{re.escape(b)}\b", t.casefold()) for b in policy["banned_terms"]):
            return _reject(op, "banned_terms")
    mag, bounds = op.get("magnitude"), policy["boost_magnitude_bounds"]
    if not isinstance(mag, (int, float)) or not (bounds["min"] <= mag <= bounds["max"]):
        return _reject(op, "boost_magnitude_bounds")
    return None


def _validate_set_top_k(op: dict, policy: dict) -> dict | None:
    bounds, value = policy["top_k_bounds"], op.get("value")
    if not isinstance(value, int) or not (bounds["min"] <= value <= bounds["max"]):
        return _reject(op, "top_k_bounds")
    return None


def validate_ops(ops: list[dict], role: dict, vocab: set[str], aliases: dict) -> tuple[list[dict], list[dict]]:
    policy = load_policy()
    validators = {
        "reweight": lambda op: _validate_reweight(op, policy),
        "promote_demote_skill": lambda op: _validate_promote(op, role, vocab, aliases),
        "hard_filter": lambda op: _validate_hard_filter(op, policy),
        "boost_penalty": lambda op: _validate_boost_penalty(op, policy),
        "set_top_k": lambda op: _validate_set_top_k(op, policy),
    }
    accepted, rejected = [], []
    for op in ops:
        kind = op.get("op")
        if kind not in policy["allowed_operations"]:
            rejected.append(_reject(op, "allowed_operations"))
            continue
        rejection = validators[kind](op)
        (rejected if rejection else accepted).append(rejection or op)
    return accepted, rejected


def apply_ops(base_weights: dict, accepted: list[dict], default_top_k: int, interpretation: str) -> tuple[dict, list[dict]]:
    weights = dict(base_weights)
    hard_filters, skill_overrides, boosts, penalties = [], [], [], []
    top_k = default_top_k
    for op in accepted:
        kind = op["op"]
        if kind == "reweight":
            weights[op["dimension"]] = op["new_weight"]
        elif kind == "promote_demote_skill":
            skill_overrides.append({"skill": op["skill"], "to_tier": op["to_tier"]})
        elif kind == "hard_filter":
            hard_filters.append({"field": op["field"], "value": op["value"]})
        elif kind == "boost_penalty":
            entry = {k: v for k, v in op.items() if k not in ("op", "direction")}
            (boosts if op["direction"] == "boost" else penalties).append(entry)
        elif kind == "set_top_k":
            top_k = op["value"]
    weights, adjustments = renormalize_and_clamp(weights, load_policy()["weight_bounds"]["max"])
    rubric = {
        "weights": weights, "hard_filters": hard_filters, "skill_overrides": skill_overrides,
        "boosts": boosts, "penalties": penalties, "top_k": top_k, "interpretation": interpretation,
    }
    rubric["hash"] = rubric_hash(rubric)
    return rubric, adjustments


def _validate_rubric_boost_entry(entry: dict, policy: dict) -> list[str]:
    errors = []
    if not set(entry["fields"]).issubset(set(policy["boost_allowed_fields"])):
        errors.append("boost field not allowed")
    if not (1 <= len(entry["match_terms"]) <= policy["boost_max_terms"]):
        errors.append("boost term count out of bounds")
    mb = policy["boost_magnitude_bounds"]
    if not (mb["min"] <= entry["magnitude"] <= mb["max"]):
        errors.append("boost magnitude out of bounds")
    for term in entry["match_terms"]:
        if any(re.search(rf"\b{re.escape(b)}\b", term.casefold()) for b in policy["banned_terms"]):
            errors.append("banned term")
    return errors


def validate_rubric(rubric: dict) -> list[str]:
    if set(rubric.keys()) != RUBRIC_KEYS:
        return ["invalid rubric keys"]
    policy = load_policy()
    errors = []
    weights, wb = rubric["weights"], policy["weight_bounds"]
    if set(weights.keys()) != SIX_DIMENSIONS:
        errors.append("invalid weight dimensions")
    elif abs(math.fsum(weights.values()) - 1.0) > 1e-6:
        errors.append("weights do not sum to 1.0")
    errors += [f"weight {k} out of bounds" for k, v in weights.items() if not (wb["min"] <= v <= wb["max"])]
    for f in rubric["hard_filters"]:
        if f["field"] not in policy["hard_filter_allowed_fields"]:
            errors.append("hard_filter field not allowed")
        elif f["field"] == "location_scope" and f["value"] not in policy["location_scope_values"]:
            errors.append("location_scope value not allowed")
    for entry in rubric["boosts"] + rubric["penalties"]:
        errors += _validate_rubric_boost_entry(entry, policy)
    tb = policy["top_k_bounds"]
    if not (tb["min"] <= rubric["top_k"] <= tb["max"]):
        errors.append("top_k out of bounds")
    if rubric["hash"] != rubric_hash(rubric):
        errors.append("hash mismatch")
    return errors
