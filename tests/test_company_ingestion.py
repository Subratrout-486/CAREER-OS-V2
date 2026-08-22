from career_os.agents.company_ingestion import CompanyIngestionRunner, CompanyTarget


class FakeScout:
    def greenhouse(self, slug):
        if slug == "broken":
            raise RuntimeError("temporary provider failure")
        return [slug]

    def lever(self, slug):
        return [slug]

    def ashby(self, slug):
        return [slug]


def test_batch_isolates_one_company_failure_and_returns_successes():
    runner = CompanyIngestionRunner(FakeScout(), max_workers=2, min_interval_seconds=0)
    results = runner.run(
        [
            CompanyTarget("Acme", "greenhouse", "acme"),
            CompanyTarget("BrokenCo", "greenhouse", "broken"),
            CompanyTarget("Beta", "lever", "beta"),
        ]
    )
    assert [r.target.company for r in results] == ["Acme", "Beta", "BrokenCo"]
    assert results[0].error is None
    assert results[1].error is None
    assert results[2].jobs == []
    assert "temporary provider failure" in results[2].error


def test_empty_batch_is_noop():
    assert CompanyIngestionRunner(FakeScout(), min_interval_seconds=0).run([]) == []


def test_unsupported_provider_is_reported_per_company():
    runner = CompanyIngestionRunner(FakeScout(), min_interval_seconds=0)
    result = runner.run([CompanyTarget("Acme", "workday", "acme")])[0]
    assert result.jobs == []
    assert "unsupported ATS provider" in result.error
