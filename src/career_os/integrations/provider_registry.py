from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Callable

from career_os.agents.ats_job_scout import ATSJobScout
from career_os.models.job import JobRecord

@dataclass(frozen=True)
class ProviderMatch:
    provider: str
    target: str

class ProviderRegistry:
    """Route supported public job portals through one zero-config interface."""
    def __init__(self, scout: ATSJobScout | None = None) -> None:
        self.scout = scout or ATSJobScout()
        self._routes: dict[str, Callable[[str], list[JobRecord]]] = {
            "greenhouse": self.scout.greenhouse,
            "lever": self.scout.lever,
            "ashby": self.scout.ashby,
            "workday": self.scout.workday,
            "rippling": self.scout.rippling,
        }

    @staticmethod
    def detect(url: str) -> ProviderMatch | None:
        parsed = urlparse(url)
        host = parsed.netloc.casefold()
        path = [part for part in parsed.path.split("/") if part]
        if "greenhouse.io" in host and path:
            return ProviderMatch("greenhouse", path[0])
        if "lever.co" in host and path:
            return ProviderMatch("lever", path[0])
        if "ashbyhq.com" in host and path:
            return ProviderMatch("ashby", path[0])
        if "myworkdayjobs.com" in host and path:
            return ProviderMatch("workday", url)
        if "rippling.com" in host and path:
            return ProviderMatch("rippling", path[-1])
        return None

    def scan(self, url: str) -> list[JobRecord]:
        match = self.detect(url)
        if match is None:
            raise ValueError(f"Unsupported or unrecognized public ATS URL: {url}")
        return self._routes[match.provider](match.target)

    def scan_many(self, urls: list[str]) -> dict[str, list[JobRecord]]:
        results: dict[str, list[JobRecord]] = {}
        for url in urls:
            try:
                results[url] = self.scan(url)
            except Exception:
                results[url] = []
        return results
