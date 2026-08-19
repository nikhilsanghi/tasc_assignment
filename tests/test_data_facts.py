from core.paths import DATA
from scripts.profile_data import compute_facts, expected_facts, load_csv


def test_data_facts_match_expected():
    cands = load_csv(DATA / "candidate_profiles.csv")
    roles = load_csv(DATA / "open_roles.csv")
    facts = compute_facts(cands, roles)
    expected = expected_facts()
    for key in expected:
        assert facts.get(key) == expected[key], f"{key}: got={facts.get(key)!r} expected={expected[key]!r}"
