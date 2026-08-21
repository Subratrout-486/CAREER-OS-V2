from __future__ import annotations

from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from career_os.models.job import JobEvidence, JobRecord, JobStatus


class JobVerifier:
    """Conservative verification signals; network access is optional and never treated as proof of freshness."""

    def verify_url(self, job: JobRecord, *, timeout: float = 10.0) -> JobRecord:
        checked_at = datetime.now(timezone.utc)
        request = Request(str(job.source_url), headers={"User-Agent": "Career-OS-V2/0.1 job-verifier"}, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                final_url = response.geturl()
                detail = f"HTTP {status}; final_url={final_url}"
                signal = "url_reachable"
                if 200 <= status < 400:
                    job.status = JobStatus.VERIFIED
                else:
                    job.status = JobStatus.GHOST
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
