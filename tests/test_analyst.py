from core.analyst import AnalystOutput, analyze


def _rec():
    return {
        "candidate_id": "C001",
        "headline": "Data analyst", "past_roles": "Analyst, Foo", "certifications": None,
        "education": None, "projects": None, "extra_curriculars": None,
        "raw": {"skills": "SQL, Python", "experience_years": "3", "location": "Dubai, UAE", "notice_period": "2 weeks notice"},
        "normalized_text": {
            "headline": "data analyst", "past_roles": "analyst, foo", "certifications": "",
            "education": "", "projects": "", "extra_curriculars": "",
            "skills": "sql, python", "experience_years": "3", "location": "dubai, uae", "notice_period": "2 weeks notice",
        },
        "dup_conflicts": {},
    }


def _scored():
    return {
        "subscores": {}, "flags": [], "auto_questions": [],
        "requirements": {"required": ["SQL", "Python"], "nice": []},
    }


def _output(overlaps=None, questions=None, data_flags=None, fit_brief="Solid analyst with relevant background overall."):
    return AnalystOutput(
        candidate_id="C001",
        overlaps=overlaps or [{"requirement": "SQL", "evidence": "SQL", "source_field": "skills", "tier": "exact"}],
        gaps=[],
        fit_brief=fit_brief,
        clarifying_questions=questions or [
            {"text": "q1", "kind": "gap"}, {"text": "q2", "kind": "gap"}, {"text": "q3", "kind": "data"},
        ],
        data_flags=data_flags or [],
        confidence="high",
    )


def test_passing_analysis_no_regeneration(fake_llm, role_r004, default_rubric):
    stub = fake_llm(_output())
    result = analyze(_rec(), role_r004, default_rubric, [], _scored())
    assert len(stub.calls) == 1
    assert result["regenerated"] is False
    assert result["critic"]["passed"] is True


def test_failing_then_passing_regenerates(fake_llm, role_r004, default_rubric):
    bad = _output(overlaps=[{"requirement": "SQL", "evidence": "NOTPRESENT", "source_field": "skills", "tier": "exact"}])
    good = _output()
    stub = fake_llm(bad, good)
    result = analyze(_rec(), role_r004, default_rubric, [], _scored())
    assert result["regenerated"] is True
    assert "<critic_failures>" in stub.calls[1][1]
    assert result["critic"]["passed"] is True


def test_two_failing_drops_overlaps_and_flags(fake_llm, role_r004, default_rubric):
    bad1 = _output(overlaps=[{"requirement": "SQL", "evidence": "NOTPRESENT", "source_field": "skills", "tier": "exact"}])
    bad2 = _output(overlaps=[{"requirement": "SQL", "evidence": "STILLBAD", "source_field": "skills", "tier": "exact"}])
    fake_llm(bad1, bad2)
    result = analyze(_rec(), role_r004, default_rubric, [], _scored())
    assert result["analysis"]["overlaps"] == []
    assert any("ungrounded citation removed" in f for f in result["analysis"]["data_flags"])
    assert result["analysis"]["confidence"] == "low"
    assert result["critic"]["passed"] is False


def test_persistent_question_mix_failure_kept_unrepaired(fake_llm, role_r004, default_rubric):
    bad_mix = [{"text": "q1", "kind": "data"}, {"text": "q2", "kind": "data"}, {"text": "q3", "kind": "gap"}]
    out1 = _output(questions=bad_mix)
    out2 = _output(questions=bad_mix)
    fake_llm(out1, out2)
    result = analyze(_rec(), role_r004, default_rubric, [], _scored())
    assert [q.model_dump() if hasattr(q, "model_dump") else q for q in result["analysis"]["clarifying_questions"]] == bad_mix
    assert any("critic_unresolved: question_mix" in f for f in result["analysis"]["data_flags"])
    assert result["critic"]["passed"] is False


def test_embedded_instruction_flag_preserved(fake_llm, role_r004, default_rubric):
    bad = _output(
        overlaps=[{"requirement": "SQL", "evidence": "NOTPRESENT", "source_field": "skills", "tier": "exact"}],
        data_flags=["embedded instruction detected"],
    )
    fake_llm(bad, bad)
    result = analyze(_rec(), role_r004, default_rubric, [], _scored())
    assert "embedded instruction detected" in result["analysis"]["data_flags"]
