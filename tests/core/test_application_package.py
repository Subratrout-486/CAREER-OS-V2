from uuid import uuid4

from career_os.core.application_package import ApplicationPackageBuilder
from career_os.models.application import ApplicationRecord
from career_os.models.fit import FitScore
from career_os.models.resume import ResumeBullet, TailoredResume


def _application() -> ApplicationRecord:
    return ApplicationRecord(
        job_id=uuid4(),
        source_url="https://example.com/jobs/1",
        company="Example",
        role="Analyst",
    )


def _resume() -> TailoredResume:
    return TailoredResume(
        summary="Analyst",
        bullets=(ResumeBullet("Used SQL.", ("c1",)),),
        matched_keywords=("SQL",),
    )


def test_hard_gaps_block_review_package():
    fit = FitScore(overall=70, hard_requirements=50, preferred_requirements=100, skills=100, hard_gaps=("Bachelor's degree",))
    package = ApplicationPackageBuilder().build(_application(), fit, _resume())
    assert not package.ready_for_review
    assert "Bachelor's degree" in package.blockers[0]


def test_clean_package_is_ready_for_review():
    fit = FitScore(overall=100, hard_requirements=100, preferred_requirements=100, skills=100)
    package = ApplicationPackageBuilder().build(_application(), fit, _resume())
    assert package.ready_for_review
    assert package.blockers == ()
