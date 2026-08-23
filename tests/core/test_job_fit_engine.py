from career_os.core.job_fit_engine import CandidateProfile, JobFitEngine
from career_os.models.jd import JDAnalysis


def test_hard_requirements_dominate_skill_match():
    jd = JDAnalysis(source_text="test", must_have_requirements=["SQL", "Bachelor's degree"], preferred_requirements=["Tableau"], skills=["SQL", "Tableau"])
    profile = CandidateProfile(skills=frozenset({"SQL", "Tableau"}), education_terms=frozenset({"B.Com"}))
    score, evaluations = JobFitEngine().evaluate(jd, profile)
    assert score.hard_requirements == 50.0
    assert "Bachelor's degree" in score.hard_gaps
    assert score.overall < 80.0
    assert any(e.requirement == "SQL" and e.status.value == "matched" for e in evaluations)


def test_strong_evidence_produces_strong_fit():
    jd = JDAnalysis(source_text="test", must_have_requirements=["SQL", "Python"], preferred_requirements=["Power BI"], skills=["SQL", "Python"])
    profile = CandidateProfile(skills=frozenset({"SQL", "Python", "Power BI"}))
    score, _ = JobFitEngine().evaluate(jd, profile)
    assert score.overall == 100.0
    assert score.recommendation == "strong_fit"
