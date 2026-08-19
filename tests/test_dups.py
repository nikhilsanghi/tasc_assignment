def test_dup_group_counts(candidates):
    groups = {c["dup_group_id"] for c in candidates if c["dup_group_id"]}
    dup_rows = [c for c in candidates if c["dup_group_id"]]
    conflicting = {c["dup_group_id"] for c in dup_rows if c["dup_conflicts"]}
    assert len(groups) == 26
    assert len(dup_rows) == 69
    assert len(conflicting) == 22


def test_c106_c014_share_a_group(candidates):
    by_id = {c["candidate_id"]: c for c in candidates}
    assert by_id["C106"]["dup_group_id"] == by_id["C014"]["dup_group_id"]
    assert by_id["C106"]["dup_group_id"] is not None


def test_effective_pool_size(candidates):
    dup_rows = sum(1 for c in candidates if c["dup_group_id"])
    groups = len({c["dup_group_id"] for c in candidates if c["dup_group_id"]})
    assert len(candidates) - dup_rows + groups == 77


def test_insufficient_data_set(candidates):
    insufficient = {c["candidate_id"] for c in candidates if c["data_quality"] < 0.5 or not c["skills"]}
    assert insufficient == {"C118", "C112"}


def test_exactly_one_unknown_id(candidates):
    unknown = [c["candidate_id"] for c in candidates if c["candidate_id"].startswith("C_UNKNOWN")]
    assert unknown == ["C_UNKNOWN_1"]
    assert "id_missing" in next(c for c in candidates if c["candidate_id"] == "C_UNKNOWN_1")["flags"]
