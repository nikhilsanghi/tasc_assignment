from core.skills import match_skill, overlap_count


def test_exact_match(aliases):
    result = match_skill("sql", ["sql", "python"], aliases)
    assert result["tier"] == "exact"
    assert result["evidence_token"] == "sql"


def test_alias_match_python_r(aliases):
    result = match_skill("python/r", ["python", "tableau"], aliases)
    assert result["tier"] == "alias"
    assert result["evidence_token"] == "python"


def test_alias_match_crm(aliases):
    result = match_skill("crm tools (salesforce/hubspot)", ["crm (salesforce)"], aliases)
    assert result["tier"] == "alias"


def test_rest_apis_not_aliased_without_similarity(aliases):
    assert match_skill("rest apis", ["rest api design"], aliases) is None


def test_no_match_returns_none(aliases):
    assert match_skill("kafka", ["python", "sql"], aliases) is None


def test_overlap_count(aliases):
    req_tokens = ["sql", "python/r", "kafka"]
    cand_tokens = ["sql", "python", "tableau"]
    assert overlap_count(req_tokens, cand_tokens, aliases) == 2


def test_semantic_match_rest_apis(aliases, similarity):
    result = match_skill("rest apis", ["rest api design"], aliases, similarity)
    assert result["tier"] == "semantic"
    assert result["evidence_token"] == "rest api design"
    assert result["similarity"] >= 0.75


def test_kafka_zero_match_with_similarity(aliases, similarity):
    assert match_skill("kafka", ["python", "sql", "jenkins", "kubernetes"], aliases, similarity) is None


def test_exact_beats_semantic(aliases, similarity):
    result = match_skill("sql", ["sql"], aliases, similarity)
    assert result["tier"] == "exact"
