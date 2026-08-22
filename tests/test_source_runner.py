from career_os.agents.source_runner import SourceRunner
from career_os.models.job import JobRecord


def job(company: str) -> JobRecord:
    return JobRecord(
        company=company,
        title="Analyst",
        source_url="https://example.com/jobs/1",
        source="test",
        canonical_key=f"{company}:1",
    )


def test_one_failed_source_does_not_abort_other_sources():
    def broken():
        raise RuntimeError("source unavailable")

    records, diagnostics = SourceRunner().run(
        [
            ("greenhouse", "broken-co", broken),
            ("lever", "working-co", lambda: [job("working-co")]),
            ("ashby", "empty-co", lambda: []),
        ]
    )

    assert [r.company for r in records] == ["working-co"]
    assert [(d.company, d.outcome.value) for d in diagnostics] == [
        ("broken-co", "FAILED"),
        ("working-co", "SUCCESS"),
        ("empty-co", "EMPTY"),
    ]
    assert "RuntimeError" in diagnostics[0].error
