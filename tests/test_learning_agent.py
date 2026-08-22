from career_os.agents.learning_agent import LearningAgent
from career_os.models.learning import LearningPriority, LearningResource


def test_learning_plan_prioritizes_gaps_and_creates_readiness_checks():
    plan = LearningAgent().build_plan("Product Support Analyst", ["SQL", "Python"])
    assert [item.skill for item in plan.objectives] == ["SQL", "Python"]
    assert plan.objectives[0].priority == LearningPriority.CRITICAL
    assert plan.objectives[1].priority == LearningPriority.HIGH
    assert plan.objectives[0].readiness_checks
    assert plan.objectives[0].practice_tasks


def test_verified_skill_is_not_reassigned_as_a_learning_gap():
    plan = LearningAgent().build_plan("Analyst", ["SQL", "Python"], verified_skills=["SQL"])
    assert [item.skill for item in plan.objectives] == ["Python"]


def test_resources_are_only_used_when_explicitly_provided():
    resource = LearningResource(
        title="Python tutorial",
        url="https://docs.python.org/3/tutorial/",
        provider="Python Docs",
        free=True,
        reason="Primary source",
    )
    plan = LearningAgent().build_plan("Analyst", ["Python"], resources_by_skill={"Python": [resource]})
    assert plan.objectives[0].resources[0].url == resource.url
    empty_plan = LearningAgent().build_plan("Analyst", ["SQL"])
    assert empty_plan.objectives[0].resources == []


def test_empty_gaps_produce_empty_plan():
    plan = LearningAgent().build_plan("Analyst", [])
    assert plan.objectives == []
