#!/usr/bin/env python3
"""Process fresh public jobs without Notion, n8n, or paid model providers.

This is the execution-path fallback for the Career OS acceptance test. It uses
Arbeitnow's free public job API, the deterministic CareerPipeline, the canonical
candidate Source of Truth, and the existing resume renderer. Results are kept in
local JSON/Arachne artifacts so the GitHub Actions run remains auditable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career_os.agents.public_job_scout import PublicJobScout
from career_os.integrations.public_job_apis import ArbeitnowAdapter
from career_os.arachne_store import ArachneResultStore
from career_os.candidate_profile import load_candidate_source_of_truth
from career_os.pipeline import CareerPipeline
from career_os.resume_artifact import (
    render_resume_html,
    render_resume_pdf,
    resume_filename,
    validate_resume_pdf,
)
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceSource, SupportStatus
from career_os.models.resume import ResumeBullet, ResumeProfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".career-os" / "direct-public-job-cycle.json"
CHECKPOINT_ROOT = ROOT / ".career-os" / "direct-public-job-checkpoints"
RESUME_ROOT = ROOT / ".career-os" / "resume"
ARACHNE_ROOT = ROOT / ".career-os" / "arachne"


def _claims(profile: dict[str, object]) -> tuple[list[EvidenceClaim], ResumeProfile]:
    source = EvidenceSource(
        "candidate/source_of_truth.json",
        "candidate_source_of_truth",
        "Canonical candidate Source of Truth",
    )
    claims: list[EvidenceClaim] = []
    bullets: list[ResumeBullet] = []
    for experience in profile["experience"]:
        company = str(experience.get("company", ""))
        title = str(experience.get("title", ""))
        for index, responsibility in enumerate(experience.get("responsibilities", [])):
            claim_id = f"exp-{company.casefold().replace(' ', '-')}-{index}"
            claim = f"{company} — {title}: {responsibility}"
            claims.append(EvidenceClaim(claim_id, claim, EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source))
            bullets.append(ResumeBullet(str(responsibility), (claim_id,)))
    for project in profile["projects"]:
        name = str(project.get("name", ""))
        for index, detail in enumerate(project.get("details", [])):
            claim_id = f"project-{name.casefold().replace(' ', '-')}-{index}"
            claim = f"{name}: {detail}"
            claims.append(EvidenceClaim(claim_id, claim, EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source))
            bullets.append(ResumeBullet(str(detail), (claim_id,)))
    for index, education in enumerate(profile.get("education", [])):
        qualification = str(education.get("qualification", ""))
        institution = str(education.get("institution", ""))
        claims.append(EvidenceClaim(
            f"education-{index}",
            f"Education: {qualification} — {institution}",
            EvidenceKind.VERIFIED,
            SupportStatus.SUPPORTED,
            1.0,
            source,
        ))
    skills = profile.get("skills_and_tools", {})
    for category, values in skills.items():
        for index, skill in enumerate(values if isinstance(values, list) else []):
            claims.append(EvidenceClaim(
                f"skill-{category}-{index}",
                f"{category}: {skill}",
                EvidenceKind.VERIFIED,
                SupportStatus.SUPPORTED,
                1.0,
                source,
            ))
    return claims, ResumeProfile(
        summary=str(profile["candidate"]["professional_summary"]),
        bullets=tuple(bullets),
    )


def _ready(result) -> tuple[bool, list[str]]:
    findings: list[str] = []
    findings.extend(f"Missing hard requirement: {gap}" for gap in result.fit.hard_gaps)
    findings.extend(f"ATS: {finding.message}" for finding in result.ats_audit.findings)
    if result.recruiter_review.recommendation != "shortlist":
        findings.append(f"Recruiter recommendation: {result.recruiter_review.recommendation}")
    return not findings and result.checkpoint.status == "completed", findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default=os.getenv(
        "CAREER_OS_PUBLIC_JOB_QUERY",
        "support engineer",
    ))
    parser.add_argument("--location", default=os.getenv("CAREER_OS_ARBEITNOW_LOCATION", ""))
    parser.add_argument("--remote-only", action="store_true")
    parser.add_argument("--max-jobs", type=int, default=int(os.getenv("CAREER_OS_DIRECT_MAX_JOBS", "8")))
    parser.add_argument("--max-age-days", type=int, default=int(os.getenv("CAREER_OS_PUBLIC_API_MAX_AGE_DAYS", "2")))
    args = parser.parse_args()

    if args.max_jobs < 1 or args.max_jobs > 20:
        raise ValueError("--max-jobs must be between 1 and 20")

    profile = load_candidate_source_of_truth()
    claims, resume = _claims(profile)
    scout = PublicJobScout()
    adapter = ArbeitnowAdapter()
    records = scout.ingest(adapter.fetch(
        query=args.query,
        location=args.location or None,
        remote_only=args.remote_only,
        pages=2,
    ))

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, args.max_age_days))
    fresh = [
        job for job in records
        if job.posted_at is None or job.posted_at.astimezone(timezone.utc) >= cutoff
    ]
    fresh.sort(key=lambda job: job.posted_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    processed: list[dict[str, object]] = []
    ready_records: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    RESUME_ROOT.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_ROOT.mkdir(parents=True, exist_ok=True)
    store = ArachneResultStore(ARACHNE_ROOT)

    for job in fresh:
        if len(processed) >= args.max_jobs:
            break
        url = str(job.job_url)
        if not url or url in seen_urls or not job.description:
            continue
        seen_urls.add(url)
        run_id = "direct-public-" + hashlib.sha256(f"{url}\0{time.time_ns()}".encode()).hexdigest()[:16]
        checkpoint_path = CHECKPOINT_ROOT / f"{run_id}.json"
        raw_job = {
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "source_url": url,
            "source": f"{job.provider} public job API",
            "description": job.description,
            "posted_at": job.posted_at,
        }
        try:
            result = CareerPipeline(checkpoint_path).run(
                run_id=run_id,
                raw_job=raw_job,
                resume=resume,
                claims=claims,
            )
            ready, findings = _ready(result)
            candidate = profile["candidate"]
            resume_name = resume_filename(str(candidate["name"]), result.job.title)
            html_path = RESUME_ROOT / resume_name.replace(".pdf", ".html")
            pdf_path = RESUME_ROOT / resume_name
            html_path.write_text(
                render_resume_html(profile, result.tailored_resume, target_role=result.job.title),
                encoding="utf-8",
            )
            render_resume_pdf(html_path.read_text(encoding="utf-8"), pdf_path)
            validation = validate_resume_pdf(pdf_path, str(candidate["name"]))
            application_artifact = result.checkpoint.artifacts.get("application_readiness", {})
            record = {
                "record_id": str(application_artifact.get("application_id") or result.job.job_id),
                "run_id": run_id,
                "status": "READY_TO_APPLY" if ready else "PROCESSED_REVIEW_REQUIRED",
                "job_id": str(result.job.job_id),
                "source_url": url,
                "company": result.job.company,
                "title": result.job.title,
                "location": result.job.location,
                "application_url": url,
                "completed_stages": list(result.checkpoint.completed_stages),
                "fit": result.fit.__dict__,
                "ats_findings": [finding.__dict__ for finding in result.ats_audit.findings],
                "recruiter_recommendation": result.recruiter_review.recommendation,
                "readiness_findings": findings,
                "resume_pdf": str(pdf_path),
                "resume_html": str(html_path),
                "resume_validation": validation,
            }
            processed.append(record)
            store.record(str(result.job.job_id), run_id, record)
            if ready:
                ready_records.append(record)
                break
        except Exception as exc:
            processed.append({
                "run_id": run_id,
                "source_url": url,
                "company": job.company,
                "title": job.title,
                "status": "PROCESSING_FAILED",
                "error": f"{type(exc).__name__}: {exc}",
            })

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "Arbeitnow free public job API",
        "query": args.query,
        "fresh_candidates": len(fresh),
        "processed_count": len(processed),
        "ready_to_apply_count": len(ready_records),
        "success": bool(ready_records),
        "ready_to_apply": ready_records,
        "processed": processed,
        "store": str(ARACHNE_ROOT / "index.json"),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": payload["success"],
        "fresh_candidates": payload["fresh_candidates"],
        "processed_count": payload["processed_count"],
        "ready_to_apply_count": payload["ready_to_apply_count"],
    }))
    return 0 if ready_records else 1


if __name__ == "__main__":
    raise SystemExit(main())
