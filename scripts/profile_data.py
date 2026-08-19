"""Verify the brief §5 data facts against the real CSVs (D-49)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import csv
import re
from collections import defaultdict

from core.paths import DATA

DUP_CONFLICT_FIELDS = [
    "experience_years", "location", "notice_period",
    "education", "past_roles", "certifications",
]
YEAR_RANGE = re.compile(r"(\d{4})\s*[‐‑‒–—-]\s*(\d{4})")


def load_csv(path: pathlib.Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def _tokens(s: str) -> list[str]:
    return [t.strip().casefold() for t in (s or "").split(",") if t.strip()]


def _canon_location(loc: str) -> tuple[str, str]:
    if "," not in (loc or ""):
        return ((loc or "").strip(), "")
    city, country = loc.split(",", 1)
    return (city.strip(), country.strip())


def _dup_groups(cands: list[dict], key_fn) -> dict:
    groups = defaultdict(list)
    for r in cands:
        groups[key_fn(r)].append(r)
    return {k: v for k, v in groups.items() if len(v) > 1}


def _group_conflicts(members: list[dict]) -> bool:
    for field in DUP_CONFLICT_FIELDS:
        if field == "location":
            vals = {_canon_location(m[field]) for m in members}
        else:
            vals = {_norm_ws(m[field]) for m in members}
        if len(vals) > 1:
            return True
    return False


def _experience_facts(cands: list[dict]) -> dict:
    anomalies, empty = set(), 0
    for r in cands:
        ey = r["experience_years"].strip()
        if not ey:
            empty += 1
        elif not re.match(r"^\d+(\.\d+)?$", ey):
            anomalies.add(ey)
    return {"experience_anomalies": anomalies, "experience_empty": empty}


def _notice_facts(cands: list[dict]) -> dict:
    vals = [r["notice_period"].strip() for r in cands]
    return {
        "notice_formats": len({v for v in vals if v}),
        "notice_empty": sum(1 for v in vals if not v),
    }


def _location_facts(cands: list[dict]) -> dict:
    vals = [r["location"] for r in cands]
    nospace = {v for v in vals if v.strip() and re.search(r",(?!\s)", v)}
    countries = {_canon_location(v)[1] for v in vals if v.strip() and _canon_location(v)[1]}
    return {
        "location_nospace_distinct": len(nospace),
        "location_empty": sum(1 for v in vals if not v.strip()),
        "countries": countries,
    }


def _dash_nulls(cands: list[dict]) -> dict:
    cols = ["certifications", "projects", "extra_curriculars"]
    return {c: sum(1 for r in cands if r[c].strip() == "-") for c in cols}


def _skills_facts(cands: list[dict], roles: list[dict]) -> dict:
    vocab = set()
    for r in cands:
        vocab.update(_tokens(r["skills"]))
    role_tokens = set()
    for r in roles:
        role_tokens.update(_tokens(r["required_skills"]) + _tokens(r["nice_to_have_skills"]))
    return {
        "skills_empty": {r["candidate_id"] for r in cands if not r["skills"].strip()},
        "vocab": len(vocab),
        "role_tokens_unique": len(role_tokens),
        "unmatched": len(role_tokens - vocab),
    }


def _dirt_facts(cands: list[dict]) -> dict:
    html_rows, moji_rows, reversed_edu, contra = set(), set(), 0, set()
    for r in cands:
        if any(re.search(r"<[a-zA-Z/][^<>]*>", v or "") for v in r.values()):
            html_rows.add(r["candidate_id"])
        if any("Ã" in (v or "") for v in r.values()):
            moji_rows.add(r["candidate_id"])
        m = YEAR_RANGE.search(r["education"])
        if m and int(m.group(1)) > int(m.group(2)):
            reversed_edu += 1
        hm = re.search(r"(\d+)\s*years?\b", r["headline"], re.I)
        ey = r["experience_years"].strip()
        if hm and re.match(r"^\d+(\.\d+)?$", ey) and abs(int(hm.group(1)) - float(ey)) > 1:
            contra.add(r["candidate_id"])
    return {
        "html_rows": html_rows,
        "mojibake_rows": moji_rows,
        "reversed_edu": reversed_edu,
        "headline_contradictions": contra,
    }


def compute_facts(cands: list[dict], roles: list[dict]) -> dict:
    raw = _dup_groups(cands, lambda r: (r["headline"], r["skills"]))
    norm = _dup_groups(cands, lambda r: _norm_ws(r["headline"]) + "|" + _norm_ws(r["skills"]))
    dup_rows = sum(len(v) for v in norm.values())
    conflicting = sum(1 for members in norm.values() if _group_conflicts(members))
    facts = {
        "cand_shape": (len(cands), len(cands[0])),
        "role_shape": (len(roles), len(roles[0])),
        "dup_raw": (len(raw), sum(len(v) for v in raw.values())),
        "dup_norm": (len(norm), dup_rows),
        "dup_norm_conflicting": conflicting,
        "pool_norm": len(cands) - dup_rows + len(norm),
        "id_empty": sum(1 for r in cands if not r["candidate_id"].strip()),
        "role_cities": {r["location"].strip() for r in roles if r["location"].strip()},
    }
    facts.update(_experience_facts(cands))
    facts.update(_notice_facts(cands))
    facts.update(_location_facts(cands))
    facts["dash_nulls"] = _dash_nulls(cands)
    facts.update(_skills_facts(cands, roles))
    facts.update(_dirt_facts(cands))
    return facts


def expected_facts() -> dict:
    return {
        "cand_shape": (120, 11),
        "role_shape": (10, 8),
        "dup_raw": (23, 61),
        "dup_norm": (26, 69),
        "dup_norm_conflicting": 22,
        "pool_norm": 77,
        "experience_anomalies": {"-2", "five years"},
        "experience_empty": 1,
        "notice_formats": 11,
        "notice_empty": 1,
        "location_nospace_distinct": 4,
        "location_empty": 1,
        "countries": {"UAE", "Egypt", "Saudi Arabia", "Jordan", "Lebanon", "Qatar"},
        "role_cities": {"Dubai", "Abu Dhabi", "Riyadh", "Cairo"},
        "id_empty": 1,
        "dash_nulls": {"certifications": 44, "projects": 66, "extra_curriculars": 44},
        "skills_empty": {"C118", "C112"},
        "vocab": 113,
        "role_tokens_unique": 52,
        "unmatched": 17,
        "html_rows": {"C120"},
        "mojibake_rows": {"C124"},
        "reversed_edu": 24,
        "headline_contradictions": {"C128"},
    }


def main() -> None:
    cands = load_csv(DATA / "candidate_profiles.csv")
    roles = load_csv(DATA / "open_roles.csv")
    facts = compute_facts(cands, roles)
    expected = expected_facts()
    failed = False
    for key in expected:
        ok = facts.get(key) == expected[key]
        failed = failed or not ok
        print(f"{'PASS' if ok else 'FAIL'}  {key}: got={facts.get(key)!r} expected={expected[key]!r}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
