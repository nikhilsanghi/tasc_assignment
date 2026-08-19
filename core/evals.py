"""D-58: pure evaluation metrics shared by scripts/run_evals.py and tests/test_evals.py."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import math


def _dcg(ids: list[str], grades: dict[str, int], k: int) -> float:
    return math.fsum(grades.get(cid, 0) / math.log2(i + 2) for i, cid in enumerate(ids[:k]))


def ndcg_at_k(ranked_ids: list[str], grades: dict[str, int], k: int) -> float:
    ideal_order = sorted(grades, key=lambda cid: -grades[cid])
    idcg = _dcg(ideal_order, grades, k)
    return _dcg(ranked_ids, grades, k) / idcg if idcg else 0.0


def recall_at_k(ranked_ids: list[str], grades: dict[str, int], k: int, threshold: int = 2) -> float:
    relevant = {cid for cid, g in grades.items() if g >= threshold}
    if not relevant:
        return 0.0
    hits = set(ranked_ids[:k]) & relevant
    return len(hits) / len(relevant)


def kendall_tau(order1: list[str], order2: list[str]) -> float:
    rank1 = {cid: i for i, cid in enumerate(order1)}
    rank2 = {cid: i for i, cid in enumerate(order2)}
    ids = list(order1)
    concordant = discordant = 0
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            sign = (rank1[a] - rank1[b]) * (rank2[a] - rank2[b])
            concordant += sign > 0
            discordant += sign < 0
    total = concordant + discordant
    return (concordant - discordant) / total if total else 1.0


def mean_rank(ids: list[str], ranked_ids: list[str]) -> float:
    positions = [ranked_ids.index(cid) + 1 for cid in ids if cid in ranked_ids]
    return math.fsum(positions) / len(positions) if positions else float("inf")


def cohens_kappa(pairs: list[tuple[int, int]]) -> float:
    n = len(pairs)
    categories = sorted({v for pair in pairs for v in pair})
    po = sum(1 for a, b in pairs if a == b) / n
    pe = 0.0
    for c in categories:
        p_a = sum(1 for a, _ in pairs if a == c) / n
        p_b = sum(1 for _, b in pairs if b == c) / n
        pe += p_a * p_b
    return (po - pe) / (1 - pe) if pe != 1 else 1.0
