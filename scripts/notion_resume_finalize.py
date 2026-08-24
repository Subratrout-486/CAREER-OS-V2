#!/usr/bin/env python3
"""Finalize processed Notion jobs with verified candidate-facing PDF resumes."""
from __future__ import annotations

import json
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from career_os.candidate_profile import load_candidate_source_of_truth
from career_os.resume_artifact import render_resume_html, render_resume_pdf, resume_filename, validate_resume_pdf
from career_os.pipeline import CareerPipeline

from notion_job_worker import (
    DEFAULT_DATA_SOURCE_ID,
    MAX_JOBS,
    NOTION_VERSION,
    prop,
    notion_request,
    fetch_queued,
    claims_from_profile,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".career-os" / "resume"
MAX_RETRIES = max(1, int(os.environ.get("CAREER_OS_NOTION_MAX_RETRIES", "5")))


def multipart_upload(file_upload_id: str, path: Path) -> dict[str, Any]:
    token = os.environ["NOTION_TOKEN"]
    boundary = "----CareerOS" + uuid.uuid4().hex
    data = path.read_bytes()
    filename = path.name
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = Request(
        f"https://api.notion.com/v1/file_uploads/{file_upload_id}/send",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Career-OS-V2/1.0",
        },
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def upload_pdf(path: Path) -> str:
    created = notion_request(
        "POST",
        "/file_uploads",
        {"mode": "single_part", "filename": path.name, "content_type": "application/pdf"},
    )
    upload_id = str(created["id"])
    multipart_upload(upload_id, path)
    deadline = time.time() + 45
    while time.time() < deadline:
        status = notion_request("GET", f"/file_uploads/{upload_id}")
        state = status.get("status")
        if state == "uploaded":
            return upload_id
        if state == "failed":
            raise RuntimeError(f"Notion PDF upload failed: {status.get('file_import_result') or status}")
        time.sleep(2)
    raise TimeoutError(f"Notion PDF upload did not reach uploaded state: {upload_id}")


def attach_pdf(page_id: str, upload_id: str, filename: str) -> None:
    notion_request(
        "PATCH",
        f"/blocks/{page_id}/children",
        {
            "children": [
                {
                    "type": "pdf",
                    "pdf": {
                        "caption": [{"type": "text", "text": {"content": f"Career OS tailored resume — {filename}"}}],
                        "type": "file_upload",
                        "file_upload": {"id": upload_id},
                    },
                }
            ]
        },
    )


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


def finalize(page: dict[str, Any], profile: dict[str, Any]) -> tuple[bool, str]:
    page_id = page["id"]
    title = prop(page, "Job") or "Untitled job"
    company = prop(page, "Company") or "Unknown employer"
    description = prop(page, "JD")
    if not description.strip():
        return False, f"missing JD: {title}"

    run_id = "notion-" + "-".join(x for x in [company, title] if x).casefold().replace(" ", "-")[:90] + "-" + page_id.replace("-", "")[:8]
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

    OUT.mkdir(parents=True, exist_ok=True)
    candidate = profile["candidate"]
    filename = resume_filename(str(candidate["name"]), result.job.title)
    html_path = OUT / filename.replace(".pdf", ".html")
    pdf_path = OUT / filename
    html_path.write_text(render_resume_html(profile, result.tailored_resume, target_role=result.job.title), encoding="utf-8")
    render_resume_pdf(html_path.read_text(encoding="utf-8"), pdf_path)
    validation = validate_resume_pdf(pdf_path, str(candidate["name"]))
    if not validation.get("valid", False):
        raise RuntimeError(f"Generated resume failed validation: {validation}")

    upload_id = upload_pdf(pdf_path)
    attach_pdf(page_id, upload_id, filename)

    findings = getattr(result.ats_audit, "findings", None) or []
    hard_gaps = getattr(result.fit, "hard_gaps", None) or []
    blockers = "; ".join(str(x) for x in hard_gaps) if hard_gaps else "; ".join(str(getattr(x, "message", x)) for x in findings)[:1900]
    ready = bool(result.application_ready) and not findings
    update_page(page_id, {
        "Processing Stage": "Ready to Apply" if ready else "Recruiter Review",
        "Status": "Ready to Apply" if ready else "Shortlisted",
        "Resume Status": "Ready" if ready else "Needs Review",
        "Fit Score": getattr(result.fit, "score", None),
        "Fit Decision": "Apply" if ready else "Apply - Verify",
        "ATS Result": "PASS" if not findings else "REVIEW",
        "Blockers": blockers,
        "Assigned Agent": "Career OS Native Worker",
        "Evidence": f"Verified candidate PDF attached to Notion: {filename}",
    })
    return ready, f"finalized: {title} -> {filename} -> {'READY_TO_APPLY' if ready else 'REVIEW'}"


def main() -> int:
    profile = load_candidate_source_of_truth()
    # Only finalize jobs already picked up by the worker. This prevents the
    # artifact stage from becoming a second intake path.
    pages = fetch_queued()
    report: list[dict[str, Any]] = []
    for page in pages[:MAX_JOBS]:
        try:
            ready, message = finalize(page, profile)
            report.append({"job_id": page.get("id"), "job": prop(page, "Job"), "ok": True, "ready": ready, "message": message})
            print(message)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"[:1900]
            report.append({"job_id": page.get("id"), "job": prop(page, "Job"), "ok": False, "ready": False, "message": message})
            print(f"FAILED SAFELY: {message}")
    path = ROOT / ".career-os" / "resume-finalize-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"results": report, "count": len(report)}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
