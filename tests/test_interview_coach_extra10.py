import pytest
from career_os.models.interview import InterviewQuestion


def test_interview_question_rejects_invalid_difficulty():
    with pytest.raises(ValueError):
        InterviewQuestion(text="Q", question_type="ROLE_SPECIFIC", competency="SQL", difficulty=4)
