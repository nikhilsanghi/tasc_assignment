"""D-56: hard-filter logic for core/scorer.py, split out to stay under 250 lines."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.skills import match_skill

MENA = {"UAE", "Saudi Arabia", "Egypt", "Jordan", "Lebanon", "Qatar"}


def _filter_notice_days_max(rec: dict, value: int) -> tuple[bool, str | None]:
    if rec["notice_kind"] in ("negotiable", "missing", "unparseable", "far_future"):
        return True, "filter_unevaluable_notice_days_max"
    return rec["notice_days"] <= value, None


def _filter_experience(rec: dict, field: str, value: float) -> tuple[bool, str | None]:
    years = rec["experience_years"]
    if years is None:
        return True, f"filter_unevaluable_{field}"
    return (years >= value if field == "experience_years_min" else years <= value), None


def _filter_must_have_skill(rec: dict, skill: str, aliases: dict, sim: dict) -> tuple[bool, str | None]:
    return match_skill(skill, rec["skills_norm"], aliases, sim) is not None, None


def _filter_location_scope(rec: dict, scope: str, role: dict) -> tuple[bool, str | None]:
    cand_loc = rec["location"]
    if not cand_loc["city"] and not cand_loc["country"]:
        return True, "filter_unevaluable_location_scope"
    if scope == "role_city":
        return cand_loc["city"] == role["location"]["city"], None
    if scope == "role_country":
        return cand_loc["country"] == role["location"]["country"], None
    return cand_loc["country"] in MENA, None


def _check_one_filter(rec: dict, f: dict, role: dict, aliases: dict, sim: dict) -> tuple[bool, str | None]:
    field, value = f["field"], f["value"]
    if field == "notice_days_max":
        return _filter_notice_days_max(rec, value)
    if field in ("experience_years_min", "experience_years_max"):
        return _filter_experience(rec, field, value)
    if field == "must_have_skill":
        return _filter_must_have_skill(rec, value, aliases, sim)
    return _filter_location_scope(rec, value, role)


def apply_hard_filters(recs: list[dict], rubric: dict, role: dict, aliases: dict, sim: dict) -> tuple[list, list, dict]:
    kept, removed, unevaluable = [], [], {}
    for rec in recs:
        keep, reason, flags = True, None, []
        for f in rubric["hard_filters"]:
            ok, flag = _check_one_filter(rec, f, role, aliases, sim)
            if flag:
                flags.append(flag)
            elif not ok:
                keep, reason = False, f["field"]
                break
        if keep:
            kept.append(rec)
            if flags:
                unevaluable[rec["candidate_id"]] = flags
        else:
            removed.append({"candidate_id": rec["candidate_id"], "reason": reason})
    return kept, removed, unevaluable
