"""Career OS adapter for the existing JobPilot local browser agent."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobPilotResult:
    submitted: bool
    state: str
    evidence: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


class JobPilotExecutor:
    """Dispatch one approved job to a user's JobPilot terminal/browser."""

    def __init__(self, *, api_url=None, api_token=None, terminal_url=None, provider=None, timeout=None, poll_interval=None):
        self.api_url = (api_url or os.getenv("JOBPILOT_API", "")).rstrip("/")
        self.api_token = api_token or os.getenv("JOBPILOT_API_TOKEN", "")
        self.terminal_url = (terminal_url or os.getenv("JOBPILOT_TERMINAL_URL", "")).rstrip("/")
        self.provider = provider or os.getenv("JOBPILOT_PROVIDER", "codex")
        self.timeout = float(timeout if timeout is not None else os.getenv("JOBPILOT_TIMEOUT_SECONDS", "900"))
        self.poll_interval = float(poll_interval if poll_interval is not None else os.getenv("JOBPILOT_POLL_SECONDS", "5"))
        if not self.api_url or not self.api_token or not self.terminal_url:
            raise RuntimeError("JobPilot executor requires JOBPILOT_API, JOBPILOT_API_TOKEN and JOBPILOT_TERMINAL_URL")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.api_url}{path}", data=data, method=method,
            headers={"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"JobPilot API {exc.code}: {detail[:1000]}") from exc

    def _terminal(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body).encode()
        req = urllib.request.Request(f"{self.terminal_url}{path}", data=data, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"JobPilot terminal {exc.code}: {detail[:1000]}") from exc

    def execute(self, job: Any, profile: dict[str, Any], resume_path: str) -> JobPilotResult:
        url = str(getattr(job, "application_url", "") or (job.get("application_url") if isinstance(job, dict) else ""))
        title = str(getattr(job, "title", "") or (job.get("title") if isinstance(job, dict) else "Career OS application"))
        company = str(getattr(job, "company", "") or (job.get("company") if isinstance(job, dict) else ""))
        if not url:
            return JobPilotResult(False, "blocked", blockers=("Application URL is missing",))

        check = self._request("GET", "/api/applied/check?" + urllib.parse.urlencode({"url": url, "title": title, "company": company}))
        if check.get("applied"):
            kind = check.get("match", {}).get("kind", "matched")
            return JobPilotResult(False, "duplicate", blockers=(f"Already applied ({kind})",))

        campaign = self._request("POST", "/api/campaigns", {"query": f"{title} at {company}", "source": "career-os", "config": {"maxApplications": 1}})
        campaign_id = str(campaign.get("campaignId", ""))
        if not campaign_id:
            raise RuntimeError("JobPilot did not return campaignId")

        job_key = f"career-os-{int(time.time() * 1000)}"
        self._request("POST", f"/api/campaigns/{campaign_id}/jobs", {
            "key": job_key, "title": title, "company": company,
            "location": str(getattr(job, "location", "") or ""), "url": url,
            "board": urllib.parse.urlparse(url).netloc, "status": "approved",
        })

        self._terminal("/sessions/start", {
            "provider": self.provider, "cols": 120, "rows": 40,
            "apiToken": self.api_token, "apiUrl": self.api_url,
            "webUrl": os.getenv("JOBPILOT_WEB", self.api_url),
        })
        self._terminal("/sessions/inject", {"command": f"/jobpilot:apply campaign {campaign_id}", "provider": self.provider})

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            applied = self._request("GET", f"/api/campaigns/{campaign_id}/jobs?status=applied&page=1&limit=10")
            item = next((x for x in (applied.get("items", []) or []) if str(x.get("key")) == job_key), None)
            if item:
                evidence = tuple(str(x).strip() for x in item.get("evidence", []) if str(x).strip())
                if evidence:
                    return JobPilotResult(True, "submitted", evidence=evidence)
                return JobPilotResult(False, "applied_without_evidence", blockers=("JobPilot reported applied without confirmation evidence",))

            failed = self._request("GET", f"/api/campaigns/{campaign_id}/jobs?status=failed&page=1&limit=10")
            item = next((x for x in (failed.get("items", []) or []) if str(x.get("key")) == job_key), None)
            if item:
                reason = str(item.get("failReason") or item.get("skipReason") or "JobPilot application failed")
                return JobPilotResult(False, "failed", blockers=(reason,))
            time.sleep(self.poll_interval)

        return JobPilotResult(False, "timeout", blockers=("JobPilot application did not reach a terminal state before timeout",))
