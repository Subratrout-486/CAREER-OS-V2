from career_os.integrations.provider_registry import ProviderMatch, ProviderRegistry


def test_detects_supported_ats_urls():
    assert ProviderRegistry.detect("https://boards.greenhouse.io/acme") == ProviderMatch("greenhouse", "acme")
    assert ProviderRegistry.detect("https://jobs.lever.co/acme") == ProviderMatch("lever", "acme")
    assert ProviderRegistry.detect("https://jobs.ashbyhq.com/acme") == ProviderMatch("ashby", "acme")
    assert ProviderRegistry.detect("https://acme.myworkdayjobs.com/en-US/careers") == ProviderMatch(
        "workday", "https://acme.myworkdayjobs.com/en-US/careers"
    )


def test_unknown_urls_are_not_routed():
    assert ProviderRegistry.detect("https://example.com/jobs") is None
