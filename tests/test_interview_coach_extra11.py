import pytest
from career_os.models.interview import AnswerScore


def test_answer_score_rejects_out_of_range_values():
    with pytest.raises(ValueError):
        AnswerScore(relevance=6, structure=0, specificity=0, evidence=0, clarity=0)
