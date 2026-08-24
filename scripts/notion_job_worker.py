#!/usr/bin/env python3
"""Process Notion Jobs through the provider-free Career OS pipeline.

The worker separates systemic intake failures from individual job failures.
Systemic failures are reported with a non-zero exit code; individual job
failures are recorded and do not stop the remaining queue.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from career_os.candidate_profile import load_candidate_source_of_truth
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceSource, SupportStatus
from career_os.models.resume import ResumeBullet, ResumeProfile
from career_os.pipeline import CareerPipeline

NOTION_VERSION = os.environ.get("NOTION_VERSION", "2026-03-11")
DEFAULT_DATA_SOURCE_ID = "8374c380-f148-41ab-a77f-eb35de20f2db"
MAX_JOBS = max(1, int(os.environ.get("CAREER_OS_MAX_JOBS", "10")))
PAGE_SIZE = min(max(1, int(os.environ.get("CAREER_OS_NOTION_PAGE_SIZE", "25"))), 100)
MAX_RETRIES = max(1, int(os.environ.get("CAREER_OS_NOTION_MAX_RETRIES", "5")))
REPORT_PATH = ROOT / ".career-os" / "notion-worker-report.json"

QUEUE_STAGES = {
    "", "Discovered", "Verified", "Analyzing", "Resume Ready", "ATS Checked", "Recruiter Review"
}
TERMINAL_STAGES = {"Ready to Apply", "Applied", "Blocked"}
TERMINAL_STATUSES = {"Applied", "Rejected", "Closed"}
RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def _sleep_for_retry(attempt: int, retry_after: str | None = None) -> None:
    if retry_after:
        try:
            delay = max(1.0, min(60.0, float(retry_after)))
        except ValueError:
            delay = min(30.0, 2.0**attempt + random.random())
    else:
        delay = min(30.0, 2.0**attempt + random.random())
    time.sleep(delay)


def notion_request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise RuntimeError("NOTION_TOKEN is not configured")
    payload = None if body is None else json.dumps(body).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        request = Request(
            "https://api.notion.com/v1" + path,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Career-OS-V2/1.0",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"Notion API {exc.code}: {detail[:1200]}")
            if exc.code in RETRYABLE_HTTP and attempt < MAX_RETRIES - 1:
                _sleep_for_retry(attempt, exc.headers.get("Retry-After"))
                continue
            raise last_error from exc
        except URLError as exc:
            last_error = RuntimeError(f"Notion network error: {exc.reason}")
            if attempt < MAX_RETRIES - 1:
                _sleep_for_retry(attempt)
                continue
            raise last_error from exc
    raise last_error or RuntimeError("Notion request failed")


def prop(page: dict[str, Any], name: str) -> Any:
    value = page.get("properties", {}).get(name, {})
    kind = value.get("type")
    data = value.get(kind, {})
    if kind in {"title", "rich_text"}:
        return "".join(x.get("plain_text", "") for x in data).strip()
    if kind == "url":
        return data or ""
    if kind == "number":
        return data
    if kind in {"select", "status"}:
        return (data or {}).get("name", "")
    if kind == "date":
        return (data or {}).get("start", "")
    return ""


def claims_from_profile(profile: dict[str, Any]) -> tuple[list[EvidenceClaim], ResumeProfile]:
    source = EvidenceSource("candidate/source_of_truth.json", "candidate_source_of_truth", "Canonical candidate Source of Truth")
    claims: list[EvidenceClaim] = []
    bullets: list[ResumeBullet] = []
    for experience in profile.get("experience", []):
        company, title = str(experience.get("company", "")), str(experience.get("title", ""))
        for index, responsibility in enumerate(experience.get("responsibilities", [])):
            claim_id = f"exp-{company.casefold().replace(' ', '-')}-{index}"
            claims.append(EvidenceClaim(claim_id, f"{company} — {title}: {responsibility}", EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source))
            bullets.append(ResumeBullet(str(responsibility), (claim_id,)))
    for project in profile.get("projects", []):
        name = str(project.get("name", ""))
        for index, detail in enumerate(project.get("details", [])):
            claim_id = f"project-{name.casefold().replace(' ', '-')}-{index}"
            claims.append(EvidenceClaim(claim_id, f"{name}: {detail}", EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source))
            bullets.append(ResumeBullet(str(detail), (claim_id,)))
    for index, education in enumerate(profile.get("education", [])):
        claim_id = f"education-{index}"
        claims.append(EvidenceClaim(claim_id, f"Education: {education.get('qualification', '')} — {education.get('institution', '')}", EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source))
    for category, values in profile.get("skills_and_tools", {}).items():
        for index, skill in enumerate(values if isinstance(values, list) else []):
            claim_id = f"skill-{category}-{index}"
            claims.append(EvidenceClaim(claim_id, f"{category}: {skill}", EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source))
    return claims, ResumeProfile(summary=str(profile["candidate"]["professional_summary"]), bullets=tuple(bullets))


def update_page(page_id: str, updates: dict[str, Any]) -> None:
    properties: dict[str, Any] = {}
    select_properties = {"Processing Stage", "Resume Status", "Fit Decision", "Role Family", "Status"}
    for name, value in updates.items():
        if name in select_properties:
            properties[name] = {"select": {"name": value}} if value else {"select": None}
        elif name == "Fit Score":
            properties[name] = {"number": float(value) if value is not None else None}
        elif name in {"Job URL", "Application URL", "Resume URL"}:
            properties[name] = {"url": value or None}
        else:
            properties[name] = {"rich_text": [{"type": "text", "text": {"content": str(value)[:1900]}}]} if value else {"rich_text": []}
    notion_request("PATCH", f"/pages/{page_id}", {"properties": properties})


def append_resume(page_id: str, tailored: Any, result: Any) -> None:
    bullets = getattr(tailored, "bullets", ())
    lines = ["Career OS — Tailored Resume", str(getattr(tailored, "summary", ""))]
    lines.extend(f"• {getattr(b, 'text', str(b))}" for b in bullets)
    lines += [f"Fit score: {getattr(result.fit, 'score', 'n/a')}", f"Application ready: {result.application_ready}"]
    children = [
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": line[:1900]}}]}}
        for line in lines if line
    ]
    for start in range(0, len(children), 50):
        notion_request("PATCH", f"/blocks/{page_id}/children", {"children": children[start:start + 50]})


def process(page: dict[str, Any], profile: dict[str, Any]) -> tuple[bool, str]:
    page_id = page["id"]
    title = prop(page, "Job") or "Untitled job"
    company = prop(page, "Company") or "Unknown employer"
    try:
        description = prop(page, "JD")
        if not description.strip():
            update_page(page_id, {
                "Processing Stage": "Blocked",
                "Resume Status": "Failed",
                "Blockers": "Full job description is missing from Notion; processing cannot safely continue.",
                "Assigned Agent": "Career OS Native Worker",
            })
            return False, f"blocked: missing JD — {title}"
        update_page(page_id, {
            "Processing Stage": "Analyzing",
            "Status": "Analyzing",
            "Resume Status": "Generating",
            "Blockers": "",
            "Assigned Agent": "Career OS Native Worker",
        })
        run_id = "notion-" + re.sub(r"[^a-z0-9]+", "-", f"{company}-{title}".casefold()).strip("-")[:90] + "-" + page_id.replace("-", "")[:8]
        checkpoint = ROOT / ".career-os" / "runs" / f"{run_id}.json"
        claims, resume = claims_from_profile(profile)
        raw_job = {
            "company": company,
            "title": title,
            "location": prop(page, "Location"),
            "source_url": prop(page, "Job URL") or prop(page, "Application URL"),
            "source": prop(page, "Source") or "Notion",
            "description": description,
        }
        result = CareerPipeline(checkpoint).run(run_id=run_id, raw_job=raw_job, resume=resume, claims=claims)
        findings = getattr(result.ats_audit, "findings", None) or []
        hard_gaps = getattr(result.fit, "hard_gaps", None) or []
        blockers = "; ".join(str(x) for x in hard_gaps) if hard_gaps else "; ".join(str(getattr(x, "message", x)) for x in findings)[:1900]
        ready = bool(result.application_ready)
        update_page(page_id, {
            "Processing Stage": "Recruiter Review",
            "Status": "Shortlisted",
            "Resume Status": "Generating" if ready else "Needs Review",
            "Fit Score": getattr(result.fit, "score", None),
            "Fit Decision": "Apply" if ready else "Apply - Verify",
            "ATS Result": "PASS" if not findings else "REVIEW",
            "Blockers": blockers,
            "Assigned Agent": "Career OS Native Worker",
            "Evidence": "Deterministic pipeline completed from the canonical candidate Source of Truth.",
        })
        append_resume(page_id, result.tailored_resume, result)
        return True, f"processed: {title}"
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"[:1900]
        try:
            update_page(page_id, {
                "Processing Stage": "Blocked",
                "Resume Status": "Failed",
                "Blockers": message,
                "Assigned Agent": "Career OS Native Worker",
            })
        except Exception as update_exc:
            print(f"WARNING: failed to write failure state for {title}: {update_exc}")
        return False, f"failed safely: {title}: {message}"


def fetch_queued() -> list[dict[str, Any]]:
    data_source_id = os.environ.get("NOTION_DATA_SOURCE_ID", DEFAULT_DATA_SOURCE_ID).replace("-", "")
    jobs: list[dict[str, Any]] = []
    cursor: str | None = None
    while len(jobs) < MAX_JOBS:
        body: dict[str, Any] = {"page_size": min(PAGE_SIZE, MAX_JOBS - len(jobs))}
        if cursor:
            body["start_cursor"] = cursor
        response = notion_request("POST", f"/data_sources/{data_source_id}/query", body)
        for page in response.get("results", []):
            stage = prop(page, "Processing Stage")
            status = prop(page, "Status")
            if status in TERMINAL_STATUSES or stage in TERMINAL_STAGES:
                continue
            if stage in QUEUE_STAGES:
                jobs.append(page)
                if len(jobs) >= MAX_JOBS:
                    break
        if len(jobs) >= MAX_JOBS or not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
        if not cursor:
            break
    return jobs


def write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    started = time.time()
    report: dict[str, Any] = {"ok": False, "started_at": started, "jobs_found": 0, "successes": 0, "failures": 0, "results": []}
    if not os.environ.get("NOTION_TOKEN"):
        report["error"] = "NOTION_TOKEN not configured"
        write_report(report)
        print("NOTION_WORKER_SYSTEM_ERROR: NOTION_TOKEN not configured")
        return 2
    try:
        profile = load_candidate_source_of_truth()
        jobs = fetch_queued()
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"[:1900]
        write_report(report)
        print(f"NOTION_WORKER_SYSTEM_ERROR: {report['error']}")
        return 2
    report["jobs_found"] = len(jobs)
    print(f"Queued Notion jobs found: {len(jobs)}")
    for page in jobs:
        ok, message = process(page, profile)
        report["successes"] += int(ok)
        report["failures"] += int(not ok)
        report["results"].append({"job_id": page.get("id"), "job": prop(page, "Job"), "ok": ok, "message": message})
        print(message)
    report["ok"] = report["failures"] == 0
    report["duration_seconds"] = round(time.time() - started, 2)
    write_report(report)
    print(f"Processed successfully: {report['successes']}/{report['jobs_found']}; failures: {report['failures']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
