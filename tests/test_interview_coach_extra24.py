from career_os.models.interview import AnswerScore


def test_perfect_answer_score_is_twenty_five():
    assert AnswerScore(relevance=5, structure=5, specificity=5, evidence=5, clarity=5).total == 25
