#!/usr/bin/env python3
"""Controlled browser application agent.

Runs only for Career OS-approved jobs. It uses verified candidate data, uploads
an existing job-specific resume, and pauses when it encounters unsupported
questions, unavailable jobs, or security verification. It never claims a
submission without confirmation evidence.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".career-os" / "application-agent-report.json"


@dataclass(frozen=True)
class ApplicationResult:
    job_id: str
    url: str
    platform: str
    state: str
    filled_fields: int
    resume_uploaded: bool
    submitted: bool
    evidence: list[str]
    blockers: list[str]


ALIASES = {
    "name": ("full name", "candidate name", "name"),
    "email": ("email address", "email"),
    "phone": ("phone number", "mobile number", "mobile", "phone"),
    "location": ("current location", "city", "location"),
    "linkedin": ("linkedin profile", "linkedin url", "linkedin"),
    "github": ("github profile", "github url", "github"),
    "website": ("personal website", "portfolio", "website"),
    "notice_period": ("notice period", "availability", "how soon can you start"),
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _field_label(locator: Any) -> str:
    parts = [
        locator.get_attribute("aria-label") or "",
        locator.get_attribute("name") or "",
        locator.get_attribute("placeholder") or "",
    ]
    return " ".join(x for x in parts if x)


def _value_for(label: str, profile: dict[str, Any]) -> str | None:
    normalized = _norm(label)
    candidate = profile.get("candidate", {})
    values = {
        "name": candidate.get("name") or candidate.get("full_name"),
        "email": candidate.get("email"),
        "phone": candidate.get("phone"),
        "location": candidate.get("location") or candidate.get("city"),
        "linkedin": candidate.get("linkedin_url"),
        "github": candidate.get("github_url"),
        "website": candidate.get("website"),
        "notice_period": candidate.get("notice_period"),
    }
    for key, aliases in ALIASES.items():
        if any(_norm(alias) in normalized for alias in aliases):
            value = values[key]
            return str(value) if value not in (None, "") else None
    return None


def detect_platform(url: str) -> str:
    host = re.sub(r"^www\.", "", url.casefold())
    if "linkedin.com" in host:
        return "linkedin"
    if "naukri.com" in host:
        return "naukri"
    return "employer_ats"


def run_application(job: dict[str, Any], profile: dict[str, Any], resume_path: str) -> ApplicationResult:
    job_id = str(job.get("id") or job.get("job_id") or "unknown")
    url = str(job.get("application_url") or "").strip()
    platform = detect_platform(url)
    approved = _norm(str(job.get("application_decision") or "")) in {
        "apply", "apply verify", "approved"
    }
    if not approved:
        return ApplicationResult(job_id, url, platform, "blocked", 0, False, False, [], ["Career OS has not approved this application."])
    if not url:
        return ApplicationResult(job_id, url, "unknown", "blocked", 0, False, False, [], ["Application URL is missing."])
    if not Path(resume_path).is_file():
        return ApplicationResult(job_id, url, platform, "blocked", 0, False, False, [], ["Job-specific resume artifact is missing."])

    blockers: list[str] = []
    evidence: list[str] = []
    filled = 0
    resume_uploaded = False
    submitted = False

    with sync_playwright() as playwright:
        cdp_url = os.environ.get("APPLICATION_BROWSER_CDP_URL", "").strip()
        browser = None
        context = None
        if cdp_url:
            browser = playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
        else:
            profile_dir = os.environ.get("APPLICATION_BROWSER_PROFILE", str(ROOT / ".career-os" / "browser-profile"))
            context = playwright.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        body = page.locator("body").inner_text(timeout=15000).casefold()
        if any(x in body for x in ("verify you are human", "security check", "captcha")):
            blockers.append("Human/security verification is present; automation paused.")
        if any(x in body for x in ("job is no longer available", "position has been filled", "job has expired")):
            blockers.append("Application page indicates the job is no longer available.")

        if not blockers:
            for field in page.locator("input, textarea").all():
                input_type = (field.get_attribute("type") or "text").casefold()
                if input_type in {"hidden", "submit", "button", "file", "checkbox", "radio", "password"}:
                    continue
                value = _value_for(_field_label(field), profile)
                if value is None:
                    continue
                try:
                    field.fill(value)
                    filled += 1
                except Exception:
                    blockers.append(f"Could not safely fill field: {_field_label(field)[:120]}")
                    break

            file_inputs = page.locator('input[type="file"]').all()
            if file_inputs:
                try:
                    file_inputs[0].set_input_files(resume_path)
                    resume_uploaded = True
                except Exception as exc:
                    blockers.append(f"Resume upload failed: {type(exc).__name__}")
            else:
                blockers.append("No resume upload control was detected.")

            # Any visible, enabled field with a label we do not know is a hard stop.
            unknown: list[str] = []
            for field in page.locator("input, textarea, select").all():
                input_type = (field.get_attribute("type") or "text").casefold()
                if input_type in {"hidden", "file", "submit", "button", "checkbox", "radio", "password"}:
                    continue
                if field.is_disabled():
                    continue
                label = _field_label(field)
                if label and _value_for(label, profile) is None:
                    unknown.append(label[:120])
            if unknown:
                blockers.append("Unknown application fields require verified answers: " + ", ".join(unknown[:8]))

        if not blockers:
            submitter = None
            for button in page.locator("button, input[type='submit']").all():
                if button.is_disabled():
                    continue
                text = _norm(button.inner_text() if (button.evaluate("el => el.tagName") == "BUTTON") else (button.get_attribute("value") or ""))
                if text in {"apply now", "submit application", "submit application now", "submit"}:
                    submitter = button
                    break
            if submitter is None:
                blockers.append("No unambiguous final-application control was detected.")
            else:
                submitter.click()
                page.wait_for_timeout(1500)
                confirmation = page.locator("body").inner_text(timeout=10000).casefold()
                submitted = any(x in confirmation for x in ("application submitted", "application received", "thanks for applying", "successfully applied"))
                evidence.append(page.url)
                if not submitted:
                    blockers.append("Submit action occurred, but no authoritative confirmation was observed.")

        evidence.append(f"page_title:{page.title()[:200]}")
        if cdp_url and browser:
            browser.close()
        else:
            context.close()

    state = "submitted" if submitted else ("paused" if blockers else "submitted_unverified")
    return ApplicationResult(job_id, url, platform, state, filled, resume_uploaded, submitted, evidence, blockers)


def main() -> int:
    job_file = os.environ.get("APPLICATION_JOB_FILE", "").strip()
    resume_file = os.environ.get("APPLICATION_RESUME_FILE", "").strip()
    profile_file = os.environ.get("APPLICATION_PROFILE_FILE", "candidate/source_of_truth.json")
    if not job_file or not resume_file:
        raise SystemExit("APPLICATION_JOB_FILE and APPLICATION_RESUME_FILE are required")
    result = run_application(_load(job_file), _load(profile_file), resume_file)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.state in {"submitted", "paused", "submitted_unverified"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
