#!/usr/bin/env python3
"""Finalize processed Notion jobs with verified candidate-facing PDF resumes."""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.request import Request, urlopen

from career_os.candidate_profile import load_candidate_source_of_truth
from career_os.models.resume import ResumeBullet, TailoredResume
from career_os.resume_artifact import render_resume_html, render_resume_pdf, resume_filename, validate_resume_pdf
from career_os.resume_library import DEFAULT_RESUME_LIBRARY_DATA_SOURCE_ID, build_resume_library_properties, next_version

from notion_job_worker import MAX_JOBS, NOTION_VERSION, prop, notion_request, fetch_queued

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".career-os" / "resume"


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
        {"children": [{"type": "pdf", "pdf": {"caption": [{"type": "text", "text": {"content": f"Career OS tailored resume — {filename}"}}], "type": "file_upload", "file_upload": {"id": upload_id}}}]},
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


def load_completed_result(checkpoint: Path) -> Any:
    """Rehydrate the completed pipeline artifacts without rerunning the pipeline."""
    if not checkpoint.exists():
        raise FileNotFoundError(f"pipeline checkpoint not found: {checkpoint}")
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    if payload.get("status") != "completed":
        raise RuntimeError(f"pipeline checkpoint is not completed: {payload.get('status')}")
    artifacts = payload.get("artifacts", {})
    required = {"job_intake", "resume_tailoring", "fit_scoring", "ats_audit", "application_readiness"}
    missing = sorted(required - artifacts.keys())
    if missing:
        raise RuntimeError(f"completed pipeline checkpoint is missing artifacts: {', '.join(missing)}")
    tailored_data = artifacts["resume_tailoring"]
    tailored = TailoredResume(
        summary=str(tailored_data.get("summary", "")),
        bullets=tuple(ResumeBullet(str(bullet.get("text", "")), tuple(bullet.get("evidence_claim_ids", []))) for bullet in tailored_data.get("bullets", [])),
        matched_keywords=tuple(tailored_data.get("matched_keywords", [])),
        omitted_claim_ids=tuple(tailored_data.get("omitted_claim_ids", [])),
        edit_trace=tuple(tailored_data.get("edit_trace", [])),
    )
    fit = SimpleNamespace(**artifacts["fit_scoring"])
    ats_findings = tuple(SimpleNamespace(**finding) for finding in artifacts["ats_audit"].get("findings", []))
    ats_score = artifacts["ats_audit"].get("score")
    ats_audit = SimpleNamespace(findings=ats_findings, score=ats_score)
    application_ready = bool(artifacts["application_readiness"].get("ready", False))
    job = SimpleNamespace(title=str(artifacts["job_intake"].get("title", "Untitled job")), role_family=str(artifacts["job_intake"].get("role_family", "Other") or "Other"))
    return SimpleNamespace(job=job, tailored_resume=tailored, fit=fit, ats_audit=ats_audit, application_ready=application_ready)


def _query_resume_library() -> list[dict[str, Any]]:
    data_source_id = os.environ.get("NOTION_RESUME_LIBRARY_DATA_SOURCE_ID", DEFAULT_RESUME_LIBRARY_DATA_SOURCE_ID).replace("-", "")
    results: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        body: dict[str, Any] = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        response = notion_request("POST", f"/data_sources/{data_source_id}/query", body)
        results.extend(response.get("results", []) or [])
        if not response.get("has_more"):
            return results
        cursor = response.get("next_cursor")
        if not cursor:
            raise RuntimeError("Resume Library pagination reported has_more without next_cursor")


def _text_property(page: dict[str, Any], name: str) -> str:
    value = (page.get("properties", {}) or {}).get(name, {})
    kind = value.get("type")
    raw = value.get(kind)
    if kind in {"title", "rich_text"}:
        return "".join(item.get("plain_text", "") for item in (raw or []))
    if kind == "select":
        return str((raw or {}).get("name", ""))
    return str(raw or "")


def _relation_ids(page: dict[str, Any], name: str) -> set[str]:
    value = (page.get("properties", {}) or {}).get(name, {})
    if value.get("type") != "relation":
        return set()
    return {str(item.get("id", "")).replace("-", "") for item in (value.get("relation") or [])}


def register_resume_library(*, job_id: str, filename: str, role_family: str, source: str, ats_score: float | None, claims_verified: bool, upload_id: str) -> str:
    """Create or reuse a Resume Library record using the job relation and filename as an idempotency key."""
    data_source_id = os.environ.get("NOTION_RESUME_LIBRARY_DATA_SOURCE_ID", DEFAULT_RESUME_LIBRARY_DATA_SOURCE_ID)
    job_key = job_id.replace("-", "")
    rows = _query_resume_library()
    versions: list[str] = []
    for row in rows:
        if job_key not in _relation_ids(row, "Job"):
            continue
        version = _text_property(row, "Version")
        if version:
            versions.append(version)
        if _text_property(row, "Resume") == filename:
            return str(row.get("id", ""))

    version = next_version(versions)
    properties = build_resume_library_properties(
        resume_name=filename,
        status="Tailored",
        role_family=role_family,
        version=version,
        source=source,
        claims_verified=claims_verified,
        notes=f"Generated and validated by Career OS Native Worker; linked to Job page {job_id}.",
        ats_score=ats_score,
        job_id=job_id,
        file_upload_id=upload_id,
        filename=filename,
    )
    try:
        created = notion_request("POST", "/pages", {"parent": {"data_source_id": data_source_id}, "properties": properties})
    except Exception:
        # POST /pages is not retried by the worker; a lost response can still
        # leave the page created, so re-query before surfacing the failure.
        for row in _query_resume_library():
            if job_key in _relation_ids(row, "Job") and _text_property(row, "Resume") == filename:
                return str(row.get("id", ""))
        raise
    created_id = str(created.get("id", ""))
    if not created_id:
        raise RuntimeError("Resume Library page creation returned no page id")
    return created_id


def finalize(page: dict[str, Any], profile: dict[str, Any]) -> tuple[bool, str]:
    page_id = page["id"]
    title = prop(page, "Job") or "Untitled job"
    company = prop(page, "Company") or "Unknown employer"
    description = prop(page, "JD")
    if not description.strip():
        return False, f"missing JD: {title}"
    if "career os" in title.casefold() or "e2e automation test" in title.casefold():
        update_page(page_id, {"Processing Stage": "Blocked", "Status": "Rejected", "Resume Status": "Failed", "Fit Decision": "Do Not Apply", "Blockers": "Internal Career OS/test job detected; candidate-facing resume generation is not permitted.", "Assigned Agent": "Career OS Native Worker"})
        return False, f"blocked internal test job: {title}"
    safe_job_key = re.sub(r"[^a-z0-9]+", "-", f"{company}-{title}".casefold()).strip("-")[:90]
    run_id = f"notion-{safe_job_key}-{page_id.replace('-', '')[:8]}"
    checkpoint = ROOT / ".career-os" / "runs" / f"{run_id}.json"
    result = load_completed_result(checkpoint)
    OUT.mkdir(parents=True, exist_ok=True)
    candidate = profile["candidate"]
    filename = resume_filename(str(candidate["name"]), result.job.title)
    html_path = OUT / filename.replace(".pdf", ".html")
    pdf_path = OUT / filename
    html_path.write_text(render_resume_html(profile, result.tailored_resume, target_role=result.job.title), encoding="utf-8")
    render_resume_pdf(html_path.read_text(encoding="utf-8"), pdf_path)
    validation = validate_resume_pdf(pdf_path, str(candidate["name"]))
    upload_id = upload_pdf(pdf_path)
    attach_pdf(page_id, upload_id, filename)
    findings = getattr(result.ats_audit, "findings", None) or []
    hard_gaps = getattr(result.fit, "hard_gaps", None) or []
    blockers = "; ".join(str(x) for x in hard_gaps) if hard_gaps else "; ".join(str(getattr(x, "message", x)) for x in findings)[:1900]
    ready = bool(result.application_ready) and not findings
    library_id = register_resume_library(
        job_id=page_id,
        filename=filename,
        role_family=str(getattr(result.job, "role_family", "") or prop(page, "Role Family") or "Other"),
        source=prop(page, "Source") or "Notion",
        ats_score=float(getattr(result.ats_audit, "score", 0)) if getattr(result.ats_audit, "score", None) is not None else None,
        claims_verified=True,
        upload_id=upload_id,
    )
    resume_reference = str(page.get("url") or f"https://www.notion.so/{page_id.replace('-', '')}")
    update_page(page_id, {
        "Processing Stage": "Ready to Apply" if ready else "Resume Finalized",
        "Status": "Ready to Apply" if ready else "Shortlisted",
        "Resume Status": "Ready" if ready else "Needs Review",
        "Fit Score": getattr(result.fit, "overall", None),
        "Fit Decision": "Apply" if ready else "Apply - Verify",
        "ATS Result": "PASS" if not findings else "REVIEW",
        "Blockers": blockers,
        "Assigned Agent": "Career OS Native Worker",
        "Evidence": f"Verified candidate PDF attached to Notion: {filename}; validation={validation}; Resume Library={library_id}",
        "Resume URL": resume_reference,
    })
    return ready, f"finalized: {title} -> {filename} -> {'READY_TO_APPLY' if ready else 'REVIEW'}"


def main() -> int:
    profile = load_candidate_source_of_truth()
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
