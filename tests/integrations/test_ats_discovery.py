from dataclasses import dataclass

from career_os.integrations.ats import RawATSJob
from career_os.integrations.ats_discovery import ATSDiscoveryService
from career_os.integrations.provider_registry import ProviderMatch


@dataclass
class FakeAdapter:
    def fetch(self, identifier, **kwargs):
        return [RawATSJob("fake", "1", "Acme", "Analyst", "Hyderabad", "JD", "https://example.com/1", None, {})]


class FakeRegistry:
    def resolve(self, url):
        return ProviderMatch("fake", "example", FakeAdapter())


def test_discovery_routes_provider_and_limits_jobs():
    result = ATSDiscoveryService(FakeRegistry()).scan("https://example.com/careers", max_jobs=1)
    assert result.provider == "fake"
    assert len(result.jobs) == 1
    records = ATSDiscoveryService.to_intake_records(result)
    assert records[0]["source"] == "fake"
    assert records[0]["title"] == "Analyst"


class EmptyRegistry:
    def resolve(self, url):
        return None


def test_unknown_provider_is_safe_empty_result():
    result = ATSDiscoveryService(EmptyRegistry()).scan("https://example.com/careers")
    assert result.provider is None
    assert result.jobs == ()
