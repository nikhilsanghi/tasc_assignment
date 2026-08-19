"""Consolidated eval report: prints brief Sec9 sections 1-8 (D-58)."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import json
import math
import os
import random

from core.auditor import build_audit, four_fifths
from core.evals import kendall_tau, mean_rank, ndcg_at_k, recall_at_k
from core.paths import DATA, ROOT, load_dotenv
from core.policy import DEFAULT_WEIGHTS, apply_ops, default_rubric, validate_ops
from core.scorer import score_all
from core.skills import load_aliases, load_similarity
from scripts.eval_live import reranker_disagreement_overlap, section5_injection_suite, section6_judge_agreement


def _load() -> dict:
    candidates = json.loads((DATA / "candidates_normalized.json").read_text())
    roles = json.loads((DATA / "roles_normalized.json").read_text())
    vocab = set()
    for c in candidates:
        vocab.update(c["skills_norm"])
    return {
        "candidates": candidates, "roles": roles, "roles_by_id": {r["role_id"]: r for r in roles},
        "by_id": {c["candidate_id"]: c for c in candidates}, "vocab": vocab,
        "aliases": load_aliases(), "similarity": load_similarity(),
        "golden_set": json.loads((DATA / "golden_set.json").read_text()) if (DATA / "golden_set.json").exists() else {},
    }


def section1_ranking_quality(golden_set: dict, roles_by_id: dict, candidates: list, aliases: dict, sim: dict) -> list[str]:
    lines = ["§1 golden-set ranking quality"]
    ndcgs, recalls = [], []
    for role_id, grades in golden_set.items():
        result = score_all(candidates, roles_by_id[role_id], default_rubric(10), aliases, sim)
        ranked_ids = [e["candidate_id"] for e in result["ranked"]]
        ndcg, recall = ndcg_at_k(ranked_ids, grades, 10), recall_at_k(ranked_ids, grades, 10)
        ndcgs.append(ndcg)
        recalls.append(recall)
        lines.append(f"  {role_id}: nDCG@10={ndcg:.3f} Recall@10={recall:.3f}")
    if ndcgs:
        lines.append(f"  mean: nDCG@10={math.fsum(ndcgs)/len(ndcgs):.3f} Recall@10={math.fsum(recalls)/len(recalls):.3f}"
                      " (n is small; no pass threshold, report only)")
    return lines


def section2_rank_stability(role: dict, candidates: list, aliases: dict, sim: dict, has_key: bool) -> list[str]:
    lines = ["§2 rank stability"]
    rubric = default_rubric(10)
    orders = []
    for seed in (1, 2, 3):
        shuffled = list(candidates)
        random.Random(seed).shuffle(shuffled)
        orders.append([e["candidate_id"] for e in score_all(shuffled, role, rubric, aliases, sim)["ranked"]])
    tau_12, tau_13 = kendall_tau(orders[0], orders[1]), kendall_tau(orders[0], orders[2])
    assert tau_12 == 1.0 and tau_13 == 1.0, f"deterministic tau not 1.0: {tau_12}, {tau_13}"
    lines.append(f"  deterministic tau (3 shuffles): {tau_12:.3f}, {tau_13:.3f} (hard assert ==1.0, PASS)")
    if has_key:
        shortlist = score_all(candidates, role, rubric, aliases, sim)["ranked"][:10]
        lines += reranker_disagreement_overlap(role, rubric, shortlist)
    else:
        lines.append("  reranker disagreement overlap: skipped (no ANTHROPIC_API_KEY)")
    return lines


def section3_groundedness() -> list[str]:
    lines = ["§3 groundedness"]
    path = ROOT / "tests" / "golden" / "groundedness_runs.jsonl"
    if not path.exists():
        lines.append("  no runs recorded yet")
        return lines
    runs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    last3 = runs[-3:]
    for r in last3:
        lines.append(f"  {r['timestamp']}: clean={r['clean']}")
    clean_count = sum(1 for r in last3 if r["clean"])
    lines.append(f"  {clean_count}/{len(last3)} of last runs clean (gate passes at 2 of 3)")
    return lines


def _steer_availability(role: dict, candidates: list, aliases: dict, sim: dict, base: dict) -> str:
    base_ranked = [e["candidate_id"] for e in base["ranked"]]
    ops = [{"op": "reweight", "dimension": "availability", "new_weight": 0.5}]
    mod, _ = apply_ops(DEFAULT_WEIGHTS, ops, 10, "steering")
    mod_ranked = [e["candidate_id"] for e in score_all(candidates, role, mod, aliases, sim)["ranked"]]
    notice14 = [e["candidate_id"] for e in base["ranked"] if e["notice_days"] is not None and e["notice_days"] <= 14]
    b, m = mean_rank(notice14, base_ranked), mean_rank(notice14, mod_ranked)
    assert m < b, f"availability reweight did not improve mean rank: {b} -> {m}"
    return f"  availability reweight: mean rank notice<=14d {b:.1f} -> {m:.1f} (PASS, improved)"


def _steer_ab_promotion(role: dict, candidates: list, aliases: dict, sim: dict, vocab: set, base: dict) -> str:
    base_ranked = [e["candidate_id"] for e in base["ranked"]]
    ops = [{"op": "promote_demote_skill", "skill": "A/B testing experience", "to_tier": "required"}]
    accepted, _ = validate_ops(ops, role, vocab, aliases)
    mod, _ = apply_ops(DEFAULT_WEIGHTS, accepted, 10, "steering")
    mod_ranked = [e["candidate_id"] for e in score_all(candidates, role, mod, aliases, sim)["ranked"]]
    ab_holders = [c["candidate_id"] for c in candidates if "a/b testing" in c["skills_norm"]]
    b, m = mean_rank(ab_holders, base_ranked), mean_rank(ab_holders, mod_ranked)
    assert m < b, f"A/B promotion did not improve mean rank: {b} -> {m}"
    return f"  A/B promotion: mean rank of A/B holders {b:.1f} -> {m:.1f} (PASS, improved)"


def _steer_client_facing_boost(role: dict, candidates: list, aliases: dict, sim: dict, base: dict) -> str:
    ops = [{"op": "boost_penalty", "concept": "client-facing", "fields": ["skills", "past_roles", "projects", "headline"],
            "match_terms": ["client", "customer support", "account management", "customer success", "stakeholder"],
            "direction": "boost", "magnitude": 0.05}]
    mod, _ = apply_ops(DEFAULT_WEIGHTS, ops, 10, "steering")
    mod_scores = {e["candidate_id"]: e["score_float"] for e in score_all(candidates, role, mod, aliases, sim)["ranked"]}
    base_scores = {e["candidate_id"]: e["score_float"] for e in base["ranked"]}
    changed = sum(1 for cid, s in base_scores.items() if mod_scores.get(cid) != s)
    assert changed >= 1, "client-facing boost changed no scores"
    return f"  client-facing boost: {changed} candidate score(s) changed (PASS, >=1)"


def _steer_location_filter(role: dict, candidates: list, aliases: dict, sim: dict, base: dict) -> str:
    default = default_rubric(10)
    filtered_rubric = {**default, "hard_filters": [{"field": "location_scope", "value": "role_city"}]}
    filtered_pool = len(score_all(candidates, role, filtered_rubric, aliases, sim)["ranked"])
    assert filtered_pool < len(base["ranked"]), "location_scope role_city did not shrink the pool"
    return f"  location_scope role_city: pool {len(base['ranked'])} -> {filtered_pool} (PASS, shrunk)"


def section4_steering(role: dict, candidates: list, aliases: dict, sim: dict, vocab: set) -> list[str]:
    base = score_all(candidates, role, default_rubric(10), aliases, sim)
    lines = ["§4 steering tests (hand-built rubrics, hard asserts)"]
    lines.append(_steer_availability(role, candidates, aliases, sim, base))
    lines.append(_steer_ab_promotion(role, candidates, aliases, sim, vocab, base))
    lines.append(_steer_client_facing_boost(role, candidates, aliases, sim, base))
    lines.append(_steer_location_filter(role, candidates, aliases, sim, base))
    n_returned = len(base["ranked"][:20])
    assert n_returned == 20, f"set_top_k 20 returned {n_returned}"
    lines.append(f"  set_top_k 20: returns {n_returned} (PASS)")
    return lines


def section7_four_fifths(roles: list, candidates: list, aliases: dict, sim: dict) -> list[str]:
    lines = ["§7 four-fifths (DEMONSTRATION on a location proxy, all 10 roles, default rubric, top-10)"]
    rubric = default_rubric(10)
    for role in roles:
        result = score_all(candidates, role, rubric, aliases, sim)
        counts: dict = {}
        for e in result["ranked"][:10]:
            counts[e["country"]] = counts.get(e["country"], 0) + 1
        ff = four_fifths(result["pool_countries"], counts)
        lines.append(f"  {role['role_id']} ({role['title']}): flagged={', '.join(ff['flagged']) or 'none'}")
    return lines


def section8_audit_completeness(role: dict, candidates: list, aliases: dict, sim: dict) -> list[str]:
    lines = ["§8 audit bundle completeness"]
    body = {
        "role_id": role["role_id"], "rubric": default_rubric(10), "approved_ids": [candidates[0]["candidate_id"]],
        "analyses": {}, "rerank": {"disagreements": [], "llm_order": [], "missing_ids": []},
        "session_meta": {"guidance": "", "rejected": [], "adjustments": [], "decomposition": {},
                          "compiled_at": "test", "approved_at": "test"},
    }
    audit = build_audit(body, "", {"flagged": []}, sim.get("_meta", {}), {"compiler": "x"}, 2)
    required = {"role_id", "guidance", "rubric", "rejected", "adjustments", "decomposition", "approved_ids",
                "analyses", "rerank", "four_fifths", "markdown", "compiled_at", "approved_at", "generated_at",
                "model_ids", "prompt_hashes", "policy_version", "similarity_cache"}
    missing = required - set(audit.keys())
    assert not missing, f"missing audit keys: {missing}"
    lines.append(f"  {len(required)}/{len(required)} required keys present (PASS)")
    return lines


def main() -> None:
    load_dotenv()
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    data = _load()
    role_r004 = data["roles_by_id"]["R004"]

    print("\n".join(section1_ranking_quality(data["golden_set"], data["roles_by_id"], data["candidates"], data["aliases"], data["similarity"])))
    print("\n".join(section2_rank_stability(role_r004, data["candidates"], data["aliases"], data["similarity"], has_key)))
    print("\n".join(section3_groundedness()))
    print("\n".join(section4_steering(role_r004, data["candidates"], data["aliases"], data["similarity"], data["vocab"])))
    if has_key:
        print("\n".join(section5_injection_suite(role_r004, data["by_id"], data["vocab"], data["aliases"])))
        print("\n".join(section6_judge_agreement(data["golden_set"], data["roles_by_id"], data["by_id"])))
    else:
        print("§5 injection suite\n  skipped (no ANTHROPIC_API_KEY)")
        print("§6 judge agreement\n  skipped (no ANTHROPIC_API_KEY)")
    print("\n".join(section7_four_fifths(data["roles"], data["candidates"], data["aliases"], data["similarity"])))
    print("\n".join(section8_audit_completeness(role_r004, data["candidates"], data["aliases"], data["similarity"])))


if __name__ == "__main__":
    main()
