from __future__ import annotations

from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from career_os.models.job import JobEvidence, JobRecord, JobStatus

_STALE_MARKERS = (
    "job is no longer available",
    "position has been filled",
    "this position has been closed",
    "job has been closed",
    "no longer accepting applications",
    "requisition has been closed",
)


def _content_signal(text: str) -> tuple[str, str] | None:
    lowered = " ".join(text.casefold().split())
    for marker in _STALE_MARKERS:
        if marker in lowered:
            return "stale_content_marker", marker
    return None


class JobVerifier:
    """Conservative verifier. Reachability alone never proves a posting is live."""

    def verify_url(self, job: JobRecord, *, timeout: float = 10.0) -> JobRecord:
        checked_at = datetime.now(timezone.utc)
        request = Request(str(job.source_url), headers={"User-Agent": "Career-OS-V2/0.1 job-verifier"}, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                final_url = response.geturl()
                body = response.read(512_000).decode("utf-8", errors="replace")
                detail = f"HTTP {status}; final_url={final_url}"
                signal = "url_reachable"
                if status in {404, 410}:
                    job.status = JobStatus.GHOST
                    signal = "url_http_error"
                elif 200 <= status < 400:
                    stale = _content_signal(body)
                    if stale:
                        signal, marker = stale
                        detail += f"; marker={marker}"
                        job.status = JobStatus.GHOST
                    else:
                        job.status = JobStatus.VERIFIED
                else:
                    job.status = JobStatus.UNKNOWN
        except HTTPError as exc:
            detail = f"HTTP {exc.code}"
            signal = "url_http_error"
            job.status = JobStatus.GHOST if exc.code in {404, 410} else JobStatus.UNKNOWN
        except (URLError, TimeoutError) as exc:
            detail = f"network_error={type(exc).__name__}"
            signal = "url_unreachable"
            job.status = JobStatus.UNKNOWN
        job.verification_evidence.append(
            JobEvidence(source_url=job.source_url, checked_at=checked_at, signal=signal, detail=detail)
        )
        return job
