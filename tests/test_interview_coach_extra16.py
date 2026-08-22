from career_os.agents.interview_coach_agent import InterviewCoachAgent
from career_os.models.interview import InterviewQuestionType


def test_generated_question_type_is_explicit():
    question = InterviewCoachAgent().generate_questions(["SQL"], [])[0]
    assert question.question_type == InterviewQuestionType.ROLE_SPECIFIC
