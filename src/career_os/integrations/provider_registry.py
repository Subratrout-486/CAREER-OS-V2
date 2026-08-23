from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from career_os.integrations.ats import AshbyAdapter, GreenhouseAdapter, LeverAdapter, RipplingAdapter, WorkdayAdapter, detect_ats
from career_os.integrations.public_ats import SmartRecruitersAdapter, TeamtailorRSSAdapter, detect_public_provider


@dataclass(frozen=True)
class ProviderMatch:
    provider: str
    identifier: str
    adapter: Any


class ATSProviderRegistry:
    """Single URL-to-provider routing layer for credential-free public ATS feeds."""

    def __init__(self) -> None:
        self._factories = {
            "greenhouse": GreenhouseAdapter,
            "lever": LeverAdapter,
            "ashby": AshbyAdapter,
            "workday": WorkdayAdapter,
            "rippling": RipplingAdapter,
            "smartrecruiters": SmartRecruitersAdapter,
            "teamtailor": TeamtailorRSSAdapter,
        }

    def resolve(self, careers_url: str) -> ProviderMatch | None:
        detected = detect_ats(careers_url) or detect_public_provider(careers_url)
        if detected is None:
            return None
        provider, identifier = detected
        factory = self._factories.get(provider)
        if factory is None:
            return None
        return ProviderMatch(provider, identifier, factory())

    def supported(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
