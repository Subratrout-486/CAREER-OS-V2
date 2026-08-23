from career_os.jd_intelligence import JDAnalyzer


def test_jd_analyzer_extracts_sections_and_bounded_skills():
    jd = """
    Product Support Analyst
    Location: Hyderabad, India
    Senior
    Responsibilities
    - Troubleshoot customer issues using SQL and REST APIs.
    - Maintain ServiceNow tickets.
    Required Qualifications
    - 2+ years of technical support experience.
    - Experience with Microsoft Excel and Oracle DB.
    Preferred Qualifications
    - PowerBI experience.
    Compensation: ₹8,00,000 - ₹12,00,000 per year
    """
    result = JDAnalyzer().analyze(jd)

    assert result.responsibilities == [
        "Troubleshoot customer issues using SQL and REST APIs.",
        "Maintain ServiceNow tickets.",
    ]
    assert "2+ years of technical support experience." in result.must_have_requirements
    assert "PowerBI experience." in result.preferred_requirements
    assert {"sql", "rest apis", "serviceNow", "excel", "oracle", "power bi"}.issubset(result.skills)
    assert result.location == "Hyderabad, India"
    assert result.work_model is None
    assert result.compensation == "₹8,00,000 - ₹12,00,000 per year"
    assert result.seniority == "Senior"


def test_skill_matching_is_bounded_not_substring_matching():
    result = JDAnalyzer().analyze("Requirements\n- Experience with pythonista workflows.")
    assert "python" not in result.skills


def test_missing_information_is_marked_ambiguous_not_invented():
    result = JDAnalyzer().analyze("We need an analyst who works with data.")
    assert result.location is None
    assert result.compensation is None
    assert result.seniority is None
    assert result.ambiguities


def test_preferences_do_not_become_must_haves():
    result = JDAnalyzer().analyze("Preferred Qualifications\n- Tableau experience.")
    assert result.preferred_requirements == ["Tableau experience."]
    assert result.must_have_requirements == []
