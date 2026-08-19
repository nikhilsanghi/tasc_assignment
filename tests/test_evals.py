from core.auditor import four_fifths
from core.evals import ndcg_at_k, recall_at_k
from scripts.run_evals import section2_rank_stability, section4_steering, section8_audit_completeness


def test_ndcg_at_k_perfect_order():
    grades = {"A": 3, "B": 2, "C": 1, "D": 0}
    assert ndcg_at_k(["A", "B", "C", "D"], grades, 4) == 1.0


def test_ndcg_at_k_worse_order_scores_lower():
    grades = {"A": 3, "B": 2, "C": 1, "D": 0}
    assert ndcg_at_k(["D", "C", "B", "A"], grades, 4) < 1.0


def test_recall_at_k():
    grades = {"A": 3, "B": 2, "C": 1, "D": 0}
    assert recall_at_k(["A", "B", "C", "D"], grades, 2) == 1.0
    assert recall_at_k(["C", "D", "A", "B"], grades, 1) == 0.0


def test_four_fifths_flag_logic():
    # equal rates -> nothing flagged
    result = four_fifths({"UAE": 10, "Egypt": 10}, {"UAE": 5, "Egypt": 5})
    assert result["flagged"] == []

    # Egypt's rate is far below UAE's -> flagged
    result = four_fifths({"UAE": 10, "Egypt": 10}, {"UAE": 5, "Egypt": 1})
    assert "Egypt" in result["flagged"]
    assert "UAE" not in result["flagged"]

    # zero pool for a country -> rate 0, not flagged as divide-by-zero error
    result = four_fifths({"UAE": 10, "Egypt": 0}, {"UAE": 5})
    assert result["rates"]["Egypt"] == 0.0


def test_deterministic_tau_is_one(role_r004, candidates, aliases, similarity):
    lines = section2_rank_stability(role_r004, candidates, aliases, similarity, has_key=False)
    assert "1.000, 1.000" in lines[1]


def test_steering_asserts_pass(role_r004, candidates, aliases, similarity):
    lines = section4_steering(role_r004, candidates, aliases, similarity, set().union(*(c["skills_norm"] for c in candidates)))
    assert all("PASS" in line for line in lines[1:])


def test_audit_completeness(role_r004, candidates, aliases, similarity):
    lines = section8_audit_completeness(role_r004, candidates, aliases, similarity)
    assert "PASS" in lines[-1]
