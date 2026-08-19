import json

from core.paths import DATA
from scripts.build_similarity_cache import MODEL, PINNED_REVISION, _candidate_tokens, _vocab_hash
from scripts.profile_data import load_csv


def _load_cache() -> dict:
    return json.loads((DATA / "skill_similarity.json").read_text())


def test_header_matches_constants():
    meta = _load_cache()["_meta"]
    assert meta["model"] == MODEL
    assert meta["revision"] == PINNED_REVISION


def test_vocab_hash_matches_current_vocabulary():
    cands = load_csv(DATA / "candidate_profiles.csv")
    assert _load_cache()["_meta"]["vocab_hash"] == _vocab_hash(_candidate_tokens(cands))


def test_rest_apis_semantic_pair():
    similarity = _load_cache()["similarity"]
    assert similarity["rest apis"]["rest api design"] >= 0.75


def test_kafka_zero_match_control():
    similarity = _load_cache()["similarity"]
    assert max(similarity["kafka"].values()) < 0.75
