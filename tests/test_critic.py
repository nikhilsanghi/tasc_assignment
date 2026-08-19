from core.critic import TEN_FIELDS, verify


def _rec(normalized_text=None):
    base = {f: "" for f in TEN_FIELDS}
    base.update(normalized_text or {})
    return {"normalized_text": base}


def _scored(required=None, nice=None):
    return {"requirements": {"required": required or ["Python"], "nice": nice or ["Tableau"]}}


def _analysis(overlaps=None, questions=None, fit_brief="A solid candidate with relevant background overall."):
    return {
        "overlaps": overlaps or [],
        "clarifying_questions": questions or [
            {"text": "q1", "kind": "gap"}, {"text": "q2", "kind": "gap"}, {"text": "q3", "kind": "data"},
        ],
        "fit_brief": fit_brief,
    }


def test_evidence_found_passes():
    rec = _rec({"skills": "python, sql"})
    analysis = _analysis(overlaps=[{"requirement": "Python", "evidence": "python", "source_field": "skills"}])
    result = verify(analysis, rec, _scored())
    assert result["passed"] is True
    assert result["failures"] == []


def test_evidence_not_found_fails():
    rec = _rec({"skills": "sql"})
    analysis = _analysis(overlaps=[{"requirement": "Python", "evidence": "python", "source_field": "skills"}])
    result = verify(analysis, rec, _scored())
    assert result["passed"] is False
    assert any(f["kind"] == "evidence_not_found" for f in result["failures"])


def test_null_field_always_fails():
    rec = _rec({"certifications": ""})
    analysis = _analysis(overlaps=[{"requirement": "Python", "evidence": "aws", "source_field": "certifications"}])
    result = verify(analysis, rec, _scored())
    assert any(f["kind"] == "evidence_not_found" for f in result["failures"])


def test_bad_requirement_fails():
    rec = _rec({"skills": "python"})
    analysis = _analysis(overlaps=[{"requirement": "Nonexistent Skill", "evidence": "python", "source_field": "skills"}])
    result = verify(analysis, rec, _scored())
    assert any(f["kind"] == "bad_requirement" for f in result["failures"])


def test_bad_source_field_fails():
    rec = _rec()
    analysis = _analysis(overlaps=[{"requirement": "Python", "evidence": "python", "source_field": "not_a_field"}])
    result = verify(analysis, rec, _scored())
    assert any(f["kind"] == "bad_source_field" for f in result["failures"])


def test_question_count_fails():
    rec = _rec()
    analysis = _analysis(questions=[{"text": "q1", "kind": "gap"}])
    result = verify(analysis, rec, _scored())
    assert any(f["kind"] == "question_count" for f in result["failures"])


def test_question_mix_fails_too_many_data():
    rec = _rec()
    analysis = _analysis(questions=[
        {"text": "q1", "kind": "data"}, {"text": "q2", "kind": "data"}, {"text": "q3", "kind": "gap"},
    ])
    result = verify(analysis, rec, _scored())
    assert any(f["kind"] == "question_mix" for f in result["failures"])


def test_superlative_fails():
    rec = _rec()
    analysis = _analysis(fit_brief="This is the best candidate we have seen.")
    result = verify(analysis, rec, _scored())
    assert any(f["kind"] == "superlative" for f in result["failures"])


def test_html_source_passes_with_stripped_evidence():
    rec = _rec({"past_roles": "hr business partner, emirates group (dubai) 2019-present: managed employee relations."})
    analysis = _analysis(overlaps=[{"requirement": "Python", "evidence": "HR Business Partner", "source_field": "past_roles"}])
    result = verify(analysis, rec, _scored())
    assert not any(f["kind"] == "evidence_not_found" for f in result["failures"])


def test_mojibake_source_passes_with_cleaned_evidence():
    rec = _rec({"headline": "customer support specialist with ã©xperience in saas"})
    analysis = _analysis(overlaps=[{"requirement": "Python", "evidence": "Ã©xperience", "source_field": "headline"}])
    result = verify(analysis, rec, _scored())
    assert not any(f["kind"] == "evidence_not_found" for f in result["failures"])


def test_promoted_non_role_skill_passes():
    rec = _rec({"skills": "kafka"})
    scored = _scored(required=["Python", "Kafka"])
    analysis = _analysis(overlaps=[{"requirement": "Kafka", "evidence": "kafka", "source_field": "skills"}])
    result = verify(analysis, rec, scored)
    assert not any(f["kind"] == "bad_requirement" for f in result["failures"])
