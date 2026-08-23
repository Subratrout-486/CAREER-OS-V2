#!/usr/bin/env python3
"""Provider-free Career OS automation runner.

This runner deliberately has no LLM/provider dependency. It discovers public ATS
postings, grounds candidate evidence in the canonical Source of Truth, runs the
existing deterministic Career OS pipeline, and writes an auditable JSON report.
It never submits applications, accepts terms, or sends credentials.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from career_os.agents.job_intake import JobIntakePipeline
from career_os.candidate_profile import load_candidate_source_of_truth
from career_os.integrations.ats_discovery import ATSDiscoveryService
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceSource, SupportStatus
from career_os.models.resume import ResumeBullet, ResumeProfile
from career_os.pipeline import CareerPipeline


def _terms(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9+#.-]+", text.casefold()) if len(token) > 2}


def _candidate_inputs(profile: dict[str, Any]) -> tuple[ResumeProfile, list[EvidenceClaim]]:
    source = EvidenceSource(
        "candidate/source_of_truth.json",
        "candidate_source_of_truth",
        "Canonical candidate Source of Truth",
    )
    claims: list[EvidenceClaim] = []
    bullets: list[ResumeBullet] = []

    summary = str(profile["candidate"].get("professional_summary", "")).strip()
    for experience_index, experience in enumerate(profile.get("experience", [])):
        company = str(experience.get("company", "")).strip()
        title = str(experience.get("title", "")).strip()
        dates = str(experience.get("dates", "")).strip()
        for responsibility_index, responsibility in enumerate(experience.get("responsibilities", [])):
            text = str(responsibility).strip()
            if not text:
                continue
            claim_id = f"experience-{experience_index}-{responsibility_index}"
            claims.append(
                EvidenceClaim(
                    claim_id=claim_id,
                    claim=f"{title} at {company} ({dates}): {text}",
                    kind=EvidenceKind.VERIFIED,
                    support=SupportStatus.SUPPORTED,
                    confidence=1.0,
                    source=source,
                )
            )
            bullets.append(ResumeBullet(text, (claim_id,)))

    for project_index, project in enumerate(profile.get("projects", [])):
        project_name = str(project.get("name", "")).strip()
        for detail_index, detail in enumerate(project.get("details", [])):
            text = str(detail).strip()
            if not text:
                continue
            claim_id = f"project-{project_index}-{detail_index}"
            claims.append(
                EvidenceClaim(
                    claim_id=claim_id,
                    claim=f"Personal project {project_name}: {text}",
                    kind=EvidenceKind.USER_PROVIDED,
                    support=SupportStatus.SUPPORTED,
                    confidence=1.0,
                    source=source,
                )
            )

    for category, skill_values in profile.get("skills_and_tools", {}).items():
        if not isinstance(skill_values, list):
            continue
        for skill_index, skill in enumerate(skill_values):
            text = str(skill).strip()
            if not text:
                continue
            claim_id = f"skill-{category}-{skill_index}"
            claims.append(
                EvidenceClaim(
                    claim_id=claim_id,
                    claim=f"Candidate evidence category {category}: {text}",
                    kind=EvidenceKind.USER_PROVIDED,
                    support=SupportStatus.SUPPORTED,
                    confidence=1.0,
                    source=source,
                )
            )

    return ResumeProfile(summary=summary, bullets=tuple(bullets)), claims


def _matches_filter(value: str, terms: list[str]) -> bool:
    if not terms:
        return True
    haystack = value.casefold()
    return any(term.casefold() in haystack for term in terms)


def _location_matches(location: str | None, allowed: list[str]) -> bool:
    if not allowed:
        return True
    return _matches_filter(location or "", allowed)


def _source_records(source_url: str, max_jobs: int) -> tuple[list[dict[str, object]], str | None]:
    try:
        result = ATSDiscoveryService().scan(source_url, max_jobs=max_jobs)
        return ATSDiscoveryService.to_intake_records(result), None
    except Exception as exc:  # one source must never erase the other source results
        return [], f"{type(exc).__name__}: {exc}"


def run(config_path: Path, candidate_path: Path, output_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    profile = load_candidate_source_of_truth(candidate_path)
    resume, claims = _candidate_inputs(profile)

    filters = config.get("filters", {})
    title_keywords = [str(item) for item in filters.get("title_keywords", [])]
    excluded_titles = [str(item) for item in filters.get("exclude_title_keywords", [])]
    locations = [str(item) for item in filters.get("locations", [])]
    max_per_source = int(filters.get("max_jobs_per_source", 100))
    max_per_run = int(filters.get("max_jobs_per_run", 100))
    min_description_chars = int(filters.get("min_description_chars", 120))
    if max_per_source <= 0 or max_per_run <= 0 or min_description_chars < 0:
        raise ValueError("job limits must be positive and min_description_chars must be non-negative")

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "mode": "provider_free_deterministic",
        "candidate_source": str(candidate_path),
        "sources": [],
        "jobs_discovered": 0,
        "jobs_evaluated": 0,
        "results": [],
        "safety": {
            "llm_provider_required": False,
            "credentials_required": False,
            "application_submission": "disabled",
            "external_terms_acceptance": "disabled",
        },
    }

    discovery = ATSDiscoveryService()
    for source_url in [str(item) for item in config.get("sources", [])]:
        if not source_url.strip():
            continue
        records, error = _source_records(source_url, max_per_source)
        source_report = {"url": source_url, "jobs": len(records), "error": error}
        report["sources"].append(source_report)
        if error:
            continue

        for raw_job in records:
            if report["jobs_evaluated"] >= max_per_run:
                break
            title = str(raw_job.get("title", ""))
            location = raw_job.get("location")
            description = str(raw_job.get("description") or "")
            if not _matches_filter(title, title_keywords):
                continue
            if any(term.casefold() in title.casefold() for term in excluded_titles):
                continue
            if not _location_matches(str(location) if location else None, locations):
                continue
            if len(description.strip()) < min_description_chars:
                continue

            normalized = JobIntakePipeline().normalize(raw_job)
            run_id = f"automation-{normalized.job_id}"
            checkpoint_path = output_path.parent / "checkpoints" / f"{normalized.job_id}.json"
            try:
                result = CareerPipeline(checkpoint_path).run(
                    run_id=run_id,
                    raw_job=raw_job,
                    resume=resume,
                    claims=claims,
                )
                report["results"].append(
                    {
                        "job_id": str(result.job.job_id),
                        "company": result.job.company,
                        "title": result.job.title,
                        "location": result.job.location,
                        "source_url": result.job.source_url,
                        "fit": {
                            "overall": result.fit.overall,
                            "hard_requirements": result.fit.hard_requirements,
                            "preferred_requirements": result.fit.preferred_requirements,
                            "skills": result.fit.skills,
                            "hard_gaps": list(result.fit.hard_gaps),
                            "preferred_gaps": list(result.fit.preferred_gaps),
                            "recommendation": result.fit.recommendation,
                        },
                        "application_ready": result.application_ready,
                        "checkpoint": str(checkpoint_path),
                    }
                )
                report["jobs_evaluated"] += 1
            except Exception as exc:
                report["results"].append(
                    {
                        "job_id": str(normalized.job_id),
                        "company": normalized.company,
                        "title": normalized.title,
                        "source_url": normalized.source_url,
                        "status": "blocked",
                        "error": f"{type(exc).__name__}: {exc}",
                        "checkpoint": str(checkpoint_path),
                    }
                )
                report["jobs_evaluated"] += 1

    report["jobs_discovered"] = sum(int(item["jobs"]) for item in report["sources"])
    report["status"] = "completed"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("config/public_ats_sources.json"))
    parser.add_argument("--candidate", type=Path, default=Path("candidate/source_of_truth.json"))
    parser.add_argument("--output", type=Path, default=Path(".career-os/automation-run.json"))
    args = parser.parse_args()
    report = run(args.sources, args.candidate, args.output)
    print(
        f"Career OS automation completed: {report['jobs_discovered']} discovered, "
        f"{report['jobs_evaluated']} evaluated, provider-free={report['safety']['llm_provider_required'] is False}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
