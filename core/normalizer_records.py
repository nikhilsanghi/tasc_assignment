"""D-53: full-record assembly for core/normalizer.py, split out to stay under 250 lines."""
import re
from collections import defaultdict

from core.policy import load_policy
from core.normalizer import (
    clean_text, parse_experience, parse_notice, parse_location,
    split_skills, norm_tokens, seniority_level, headline_experience_claim,
    dup_key, canonical_value, data_quality,
)
from core.normalizer_tables import FREE_TEXT_FIELDS, NON_ID_FIELDS, DUP_CONFLICT_FIELDS, YEAR_RANGE_RE


def _assign_ids(raw_rows: list[dict]) -> list[str]:
    ids, seen_unknown = [], 0
    for row in raw_rows:
        cid = (row.get("candidate_id") or "").strip()
        if not cid:
            seen_unknown += 1
            cid = f"C_UNKNOWN_{seen_unknown}"
        ids.append(cid)
    return ids


def _cluster_duplicates(raw_rows: list[dict]) -> dict[str, list[int]]:
    groups = defaultdict(list)
    for i, row in enumerate(raw_rows):
        groups[dup_key(row["headline"], row["skills"])].append(i)
    return {key: idxs for key, idxs in groups.items() if len(idxs) > 1}


def _group_conflicts(raw_rows: list[dict], idxs: list[int]) -> dict[str, list[str]]:
    conflicts = {}
    for field in DUP_CONFLICT_FIELDS:
        values = sorted({canonical_value(field, raw_rows[i][field]) for i in idxs})
        if len(values) > 1:
            conflicts[field] = values
    return conflicts


def _proxy_flags(cleaned_fields: dict, policy: dict) -> list[str]:
    mask = policy["proxy_scan_mask"]
    terms = policy["proxy_scan_terms"]
    for text in cleaned_fields.values():
        if not text:
            continue
        masked = text.casefold()
        for phrase in mask:
            masked = masked.replace(phrase, "")
        for term in terms:
            if re.search(rf"\b{re.escape(term)}\b", masked):
                return ["proxy_language"]
    return []


def _normalized_text(row: dict, cleaned: dict) -> dict:
    out = {}
    for field in NON_ID_FIELDS:
        text = cleaned[field] if field in cleaned else row.get(field)
        if text == "-":
            text = None
        out[field] = (text or "").casefold()
    return out


def _clean_free_text(row: dict) -> tuple[dict, list[str]]:
    cleaned, flags = {}, []
    for field in FREE_TEXT_FIELDS:
        cleaned[field], f = clean_text(row[field])
        flags += f
    return cleaned, flags


def _build_record(row: dict, cid: str, dgid: str | None, members: list[str], conflicts: dict) -> dict:
    flags = [f"dup_conflict_{f}" for f in conflicts]
    cleaned, clean_flags = _clean_free_text(row)
    flags += clean_flags
    experience_years, exp_flags = parse_experience(row["experience_years"])
    flags += exp_flags
    notice_days, notice_kind = parse_notice(row["notice_period"])
    location, loc_flags = parse_location(row["location"])
    flags += loc_flags
    skills = split_skills(row["skills"])
    if not (row.get("candidate_id") or "").strip():
        flags.append("id_missing")
    claim = headline_experience_claim(row["headline"])
    if claim is not None and experience_years is not None and abs(claim - experience_years) >= 3:
        flags.append("headline_experience_conflict")
    m = YEAR_RANGE_RE.search(row["education"] or "")
    if m and int(m.group(1)) > int(m.group(2)):
        flags.append("education_years_reversed")
    flags += _proxy_flags(cleaned, load_policy())
    return {
        "candidate_id": cid, "dup_group_id": dgid, "dup_members": members, "dup_conflicts": conflicts,
        "headline": cleaned["headline"], "skills": skills, "skills_norm": norm_tokens(skills),
        "experience_years": experience_years, "seniority_level": seniority_level(row["headline"], row["past_roles"]),
        "past_roles": cleaned["past_roles"], "certifications": cleaned["certifications"],
        "education": cleaned["education"], "projects": cleaned["projects"], "extra_curriculars": cleaned["extra_curriculars"],
        "location": location, "notice_days": notice_days, "notice_kind": notice_kind,
        "data_quality": data_quality(row), "flags": sorted(set(flags)),
        "normalized_text": _normalized_text(row, cleaned), "raw": dict(row),
    }


def normalize_all(raw_rows: list[dict]) -> list[dict]:
    ids = _assign_ids(raw_rows)
    dup_groups = _cluster_duplicates(raw_rows)
    group_id_by_index, members_by_index, conflicts_by_index = {}, {}, {}
    for i, (key, idxs) in enumerate(dup_groups.items()):
        gid = f"G{i + 1:02d}"
        conflicts = _group_conflicts(raw_rows, idxs)
        for idx in idxs:
            group_id_by_index[idx] = gid
            members_by_index[idx] = [ids[j] for j in idxs]
            conflicts_by_index[idx] = conflicts
    return [
        _build_record(row, ids[i], group_id_by_index.get(i), members_by_index.get(i, []), conflicts_by_index.get(i, {}))
        for i, row in enumerate(raw_rows)
    ]
