#!/usr/bin/env python3
"""Execute user-approved Career OS applications and persist verified outcomes."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import notion_job_worker
from career_os.candidate_profile import load_candidate_source_of_truth
from career_os.resume_artifact import resume_filename
from career_os.application.submission_adapter import ApplicationSubmissionAdapter

JOBS_DS = os.environ.get("NOTION_JOBS_DATA_SOURCE_ID", "8374c380-f148-41ab-a77f-eb35de20f2db")
APPLICATIONS_DS = os.environ.get("NOTION_APPLICATIONS_DATA_SOURCE_ID", "2a4c9821-f380-4a3d-a329-b8dcff959935")
REPORT = ROOT / ".career-os" / "application-worker-report.json"


def _text(page: dict[str, Any], name: str) -> str:
    prop = (page.get("properties", {}) or {}).get(name, {})
    kind = prop.get("type")
    raw = prop.get(kind)
    if kind in {"title", "rich_text"}:
        return "".join(x.get("plain_text", "") for x in (raw or []))
    if kind == "select":
        return str((raw or {}).get("name", ""))
    if kind == "url":
        return str(raw or "")
    return str(raw or "")


def _query(ds: str, query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    """Query a Notion data source without sending invalid null filters."""
    body: dict[str, Any] = {"page_size": 100}
    response = notion_job_worker.notion_request(
        "POST", f"/data_sources/{ds.replace('-', '')}/query", body
    )
    return response.get("results", []) or []


def _eligible_jobs() -> list[dict[str, Any]]:
    rows = _query(JOBS_DS, "")
    return [
        row for row in rows
        if _text(row, "Processing Stage") == "Ready to Apply"
        and _text(row, "Status") == "Ready to Apply"
        and _text(row, "Resume Status") == "Ready"
        and _text(row, "Fit Decision") == "Apply"
        and _text(row, "Application URL")
    ]


def _existing_application(job_url: str) -> dict[str, Any] | None:
    response = notion_job_worker.notion_request(
        "POST", f"/data_sources/{APPLICATIONS_DS.replace('-', '')}/query", {"page_size": 100}
    )
    for row in response.get("results", []) or []:
        if _text(row, "Job URL") == job_url:
            return row
    return None


def _application_properties(job: dict[str, Any], result: Any, resume_name: str) -> dict[str, Any]:
    job_url = _text(job, "Job URL")
    evidence = "; ".join(result.evidence)
    title = f"{_text(job, 'Company')} — {_text(job, 'Job')}"
    return {
        "Application": {"title": [{"type": "text", "text": {"content": title[:1900]}}]},
        "Application URL": {"url": _text(job, "Application URL")},
        "Job URL": {"url": job_url},
        "Resume": {"rich_text": [{"type": "text", "text": {"content": resume_name[:1900]}}]},
        "Status": {"select": {"name": "Applied"}},
        "Submitted Date": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
        "Notes": {"rich_text": [{"type": "text", "text": {"content": f"Verified browser submission. Evidence: {evidence}"[:1900]}}]},
        "Blockers": {"rich_text": []},
    }


def _create_application(job: dict[str, Any], result: Any, resume_name: str) -> str:
    job_url = _text(job, "Job URL")
    properties = _application_properties(job, result, resume_name)
    existing = _existing_application(job_url)
    if existing:
        page_id = str(existing.get("id", ""))
        if page_id:
            notion_job_worker.notion_request("PATCH", f"/pages/{page_id}", {"properties": properties})
        return page_id
    try:
        created = notion_job_worker.notion_request(
            "POST", "/pages", {"parent": {"data_source_id": APPLICATIONS_DS}, "properties": properties}
        )
    except Exception:
        existing = _existing_application(job_url)
        if existing:
            page_id = str(existing.get("id", ""))
            if page_id:
                notion_job_worker.notion_request("PATCH", f"/pages/{page_id}", {"properties": properties})
            return page_id
        raise
    return str(created.get("id", ""))


def main() -> int:
    profile = load_candidate_source_of_truth()
    candidates = _eligible_jobs()
    report: list[dict[str, Any]] = []
    if not candidates:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({"success": True, "candidates": 0, "results": []}, indent=2) + "\n")
        print("No user-approved application candidates.")
        return 0

    # CI validates the backend control plane, not an authenticated browser session.
    # Never attempt a real application from CI; production/local runs still require
    # the explicit browser/CDP configuration and the existing approval/evidence gates.
    if os.environ.get("CI", "").lower() == "true" and not os.environ.get("APPLICATION_BROWSER_CDP_URL", "").strip():
        report = [
            {
                "job_id": page.get("id"),
                "job": _text(page, "Job"),
                "company": _text(page, "Company"),
                "submitted": False,
                "state": "deferred",
                "blockers": ["Authenticated browser handoff is unavailable in CI; application execution deferred."],
            }
            for page in candidates
        ]
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({"success": True, "candidates": len(candidates), "results": report}, indent=2) + "\n")
        print(json.dumps({"success": True, "candidates": len(candidates), "results": report}, indent=2))
        return 0

    adapter = ApplicationSubmissionAdapter()
    for page in candidates:
        title = _text(page, "Job")
        company = _text(page, "Company")
        filename = resume_filename(str(profile["candidate"]["name"]), title)
        resume_path = ROOT / ".career-os" / "resume" / filename
        job = {"id": page.get("id"), "application_url": _text(page, "Application URL"), "application_decision": "apply"}
        try:
            result = adapter.execute(
                application=_application_record_from_page(page), job=job, profile=profile, resume_path=str(resume_path)
            )
            row = {"job_id": page.get("id"), "job": title, "company": company, "submitted": result.submitted, "state": result.state, "evidence": list(result.evidence), "blockers": list(result.blockers)}
            if result.submitted:
                application_id = _create_application(page, result, filename)
                notion_job_worker.notion_request(
                    "PATCH", f"/pages/{page['id']}", {"properties": {
                        "Processing Stage": {"select": {"name": "Applied"}},
                        "Status": {"select": {"name": "Applied"}},
                        "Blockers": {"rich_text": []},
                        "Evidence": {"rich_text": [{"type": "text", "text": {"content": f"Submitted; Application page {application_id}; evidence: {'; '.join(result.evidence)}"[:1900]}}]},
                    }}
                )
                row["application_id"] = application_id
            report.append(row)
        except Exception as exc:
            report.append({"job_id": page.get("id"), "job": title, "company": company, "submitted": False, "state": "failed", "error": f"{type(exc).__name__}: {exc}"[:1900]})

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"success": all(r.get("submitted") for r in report), "candidates": len(candidates), "results": report}, indent=2) + "\n")
    return 0 if all(r.get("submitted") for r in report) else 1


def _application_record_from_page(page: dict[str, Any]):
    from career_os.agents.application_manager import ApplicationManager
    from career_os.models.job import JobRecord, SourceType, canonical_job_key

    url = _text(page, "Job URL") or _text(page, "Application URL")
    job = JobRecord(
        company=_text(page, "Company"), title=_text(page, "Job"), location=_text(page, "Location"),
        source_url=url, source=_text(page, "Source") or "Notion", source_type=SourceType.OFFICIAL_CAREER_PAGE,
        canonical_key=canonical_job_key(_text(page, "Company"), _text(page, "Job"), _text(page, "Location"), url),
    )
    manager = ApplicationManager()
    record = manager.create(job, resume_version=_text(page, "Resume URL") or "notion")
    manager.mark_ready(record)
    manager.approve(record)
    return record


if __name__ == "__main__":
    raise SystemExit(main())
