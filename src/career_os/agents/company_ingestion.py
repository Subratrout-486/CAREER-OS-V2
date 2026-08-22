from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Callable

from career_os.agents.ats_job_scout import ATSJobScout
from career_os.models.job import JobRecord


@dataclass(frozen=True)
class CompanyTarget:
    company: str
    provider: str
    slug: str


@dataclass(frozen=True)
class CompanyIngestionResult:
    target: CompanyTarget
    jobs: list[JobRecord]
    error: str | None = None


class CompanyIngestionRunner:
    """Run independent ATS boards with bounded concurrency and per-company isolation."""

    def __init__(
        self,
        scout: ATSJobScout | None = None,
        *,
        max_workers: int = 4,
        min_interval_seconds: float = 0.25,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be >= 0")
        self.scout = scout or ATSJobScout()
        self.max_workers = max_workers
        self.min_interval_seconds = min_interval_seconds
        self._last_request = 0.0

    def _throttle(self) -> None:
        if self.min_interval_seconds == 0:
            return
        now = monotonic()
        wait = self.min_interval_seconds - (now - self._last_request)
        if wait > 0:
            sleep(wait)
        self._last_request = monotonic()

    def _fetch(self, target: CompanyTarget) -> list[JobRecord]:
        self._throttle()
        fetchers: dict[str, Callable[[str], list[JobRecord]]] = {
            "greenhouse": self.scout.greenhouse,
            "lever": self.scout.lever,
            "ashby": self.scout.ashby,
        }
        try:
            return fetchers[target.provider.casefold()](target.slug)
        except KeyError as exc:
            raise ValueError(f"unsupported ATS provider: {target.provider}") from exc

    def run(self, targets: list[CompanyTarget]) -> list[CompanyIngestionResult]:
        if not targets:
            return []
        results: list[CompanyIngestionResult] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(targets))) as pool:
            futures = {pool.submit(self._fetch, target): target for target in targets}
            for future in as_completed(futures):
                target = futures[future]
                try:
                    results.append(CompanyIngestionResult(target=target, jobs=future.result()))
                except Exception as exc:  # isolate one company's failure from the batch
                    results.append(CompanyIngestionResult(target=target, jobs=[], error=f"{type(exc).__name__}: {exc}"))
        return sorted(results, key=lambda result: (result.target.company.casefold(), result.target.provider.casefold()))
