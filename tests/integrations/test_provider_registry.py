from career_os.integrations.provider_registry import ATSProviderRegistry


def test_registry_resolves_existing_and_new_public_providers():
    registry = ATSProviderRegistry()
    assert registry.resolve("https://job-boards.greenhouse.io/example").provider == "greenhouse"
    assert registry.resolve("https://jobs.ashbyhq.com/example").provider == "ashby"
    assert registry.resolve("https://example.teamtailor.com").provider == "teamtailor"
    assert registry.resolve("https://jobs.smartrecruiters.com/Example").provider == "smartrecruiters"


def test_registry_leaves_unknown_hosts_unresolved():
    assert ATSProviderRegistry().resolve("https://example.com/careers") is None


def test_supported_providers_are_stable_and_sorted():
    supported = ATSProviderRegistry().supported()
    assert supported == tuple(sorted(supported))
    assert {"greenhouse", "lever", "ashby", "workday", "rippling", "smartrecruiters", "teamtailor"}.issubset(supported)
