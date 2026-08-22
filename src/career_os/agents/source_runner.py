from __future__ import annotations

from collections.abc import Callable, Iterable

from career_os.models.job import JobRecord
from career_os.models.source_run import SourceOutcome, SourceRunDiagnostic


Fetcher = Callable[[], Iterable[JobRecord]]


class SourceRunner:
    """Run independent sources without allowing one failure to abort the crawl."""

    def run(self, sources: Iterable[tuple[str, str, Fetcher]]) -> tuple[list[JobRecord], list[SourceRunDiagnostic]]:
        records: list[JobRecord] = []
        diagnostics: list[SourceRunDiagnostic] = []

        for source, company, fetch in sources:
            diagnostic = SourceRunDiagnostic(source=source, company=company)
            try:
                fetched = list(fetch())
                raw_count = len(fetched)
                duplicate_count = sum(1 for job in fetched if job.duplicate_of is not None)
                normalized_count = raw_count
                diagnostic.finish(
                    outcome=SourceOutcome.EMPTY if not fetched else SourceOutcome.SUCCESS,
                    raw_found=raw_count,
                    normalized_found=normalized_count,
                    duplicates=duplicate_count,
                )
                records.extend(fetched)
            except Exception as exc:  # source isolation: one broken board must not stop the crawl
                diagnostic.finish(
                    outcome=SourceOutcome.FAILED,
                    raw_found=0,
                    normalized_found=0,
                    error=f"{type(exc).__name__}: {exc}",
                )
            diagnostics.append(diagnostic)

        return records, diagnostics
