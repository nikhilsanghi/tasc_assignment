"""Generate the golden-set labeling sheet for hand grading."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import argparse
import csv
import json
import random

from core.paths import ROOT, DATA
from core.skills import load_aliases, overlap_count

ROLE_IDS = ["R004", "R003"]
GRADING_RUBRIC = "3 = would interview today, 2 = worth a screen, 1 = weak/stretch, 0 = not a fit"


def _load_data() -> tuple[list[dict], dict]:
    cands = json.loads((DATA / "candidates_normalized.json").read_text())
    roles = {r["role_id"]: r for r in json.loads((DATA / "roles_normalized.json").read_text())}
    return cands, roles


def _pick_candidates(role: dict, cands: list[dict], aliases: dict) -> list[dict]:
    req_tokens = role["required_norm"] + role["nice_norm"]
    scored = sorted(cands, key=lambda c: (-overlap_count(req_tokens, c["skills_norm"], aliases), c["candidate_id"]))
    top8 = scored[:8]
    top8_ids = {c["candidate_id"] for c in top8}
    rest = [c for c in cands if c["candidate_id"] not in top8_ids]
    extra4 = random.Random(42).sample(rest, 4)
    return top8 + extra4


def _write_markdown(picks_by_role: dict) -> None:
    lines = ["# labeling_sheet.md - golden-set grading (private)", "", f"Grading rubric: {GRADING_RUBRIC}", ""]
    for role_id, picks in picks_by_role.items():
        lines.append(f"## {role_id}")
        lines.append("| candidate_id | headline | skills | experience | location | notice | grade (0-3) | notes |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for c in picks:
            loc = f"{c['location']['city'] or ''}, {c['location']['country'] or ''}"
            lines.append(f"| {c['candidate_id']} | {c['headline'] or ''} | {', '.join(c['skills'])} | "
                          f"{c['experience_years']} | {loc} | {c['notice_days']} | | |")
        lines.append("")
    (ROOT / "private" / "labeling_sheet.md").write_text("\n".join(lines))


def _write_csv(picks_by_role: dict) -> None:
    with open(ROOT / "private" / "labeling_sheet.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["role_id", "candidate_id", "grade", "notes"])
        for role_id, picks in picks_by_role.items():
            for c in picks:
                writer.writerow([role_id, c["candidate_id"], "", ""])


def main() -> None:
    cands, roles = _load_data()
    aliases = load_aliases()
    picks_by_role = {rid: _pick_candidates(roles[rid], cands, aliases) for rid in ROLE_IDS}
    _write_markdown(picks_by_role)
    _write_csv(picks_by_role)
    print(f"wrote private/labeling_sheet.md and .csv for {ROLE_IDS}")


def import_golden_set() -> None:
    golden: dict = {}
    with open(ROOT / "private" / "labeling_sheet.csv", newline="") as f:
        for row in csv.DictReader(f):
            if not row["grade"].strip():
                continue
            golden.setdefault(row["role_id"], {})[row["candidate_id"]] = int(row["grade"])
    (DATA / "golden_set.json").write_text(json.dumps(golden, sort_keys=True, indent=1))
    print(f"wrote data/golden_set.json with {sum(len(v) for v in golden.values())} grades")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--import", dest="do_import", action="store_true")
    args = parser.parse_args()
    import_golden_set() if args.do_import else main()
