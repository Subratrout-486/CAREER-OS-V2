#!/usr/bin/env python3
"""Controlled browser application agent.

This agent executes only applications that Career OS has explicitly approved.
It fills fields for which verified candidate data exists, uploads the selected
job-specific resume, and refuses to guess unknown facts. It records a local
execution report and never marks an application as submitted unless a
submission confirmation is observed.

Browser authentication is intentionally external: use an already-authenticated
Playwright/Chromium profile or a trusted CDP endpoint. Credentials/cookies are
never stored in the repository.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
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


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("full name", "name", "candidate name"),
    "email": ("email", "email address"),
    "phone": ("phone", "phone number", "mobile", "mobile number"),
    "location": ("location", "city", "current location", "address"),
    "linkedin": ("linkedin", "linkedin url", "linkedin profile"),
    "github": ("github", "github url", "github profile"),
    "website": ("website", "portfolio", "personal website"),
    "notice_period": ("notice period", "availability", "how soon can you start"),
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _label_for_input(locator: Any) -> str:
    try:
        aria = locator.get_attribute("aria-label") or ""
        name = locator.get_attribute("name") or ""
        placeholder = locator.get_attribute("placeholder") or ""
        return " ".join(x for x in (aria, name, placeholder) if x)
    except Exception:
        return ""


def _field_value(label: str, profile: dict[str, Any]) -> str | None:
    normalized = _norm(label)
    candidate = profile.get("candidate", {})
    direct = {
        "name": candidate.get("name") or candidate.get("full_name"),
        "email": candidate.get("email"),
        "phone": candidate.get("phone"),
        "location": candidate.get("location") or candidate.get("city"),
        "linkedin": candidate.get("linkedin_url"),
        "github": candidate.get("github_url"),
        "website": candidate.get("website"),
        "notice_period": candidate.get("notice_period"),
    }
    for key, aliases in FIELD_ALIASES.items():
        if any(_norm(alias) in normalized for alias in aliases):
            value = direct.get(key)
            return str(value) if value not in (None, "") else None
    return None


def detect_platform(url: str) -> str:
    host = re.sub(r"^www\\.", "", url.casefold())
    if "linkedin.com" in host:
        return "linkedin"
    if "naukri.com" in host:
        return "naukri"
    return "employer_ats"


def run_application(job: dict[str, Any], profile: dict[str, Any], resume_path: str) -> ApplicationResult:
    job_id = str(job.get("id") or job.get("job_id") or "unknown")
    url = str(job.get("application_url") or "").strip()
    approved = str(job.get("application_decision") or "").casefold() in {"apply", "apply – verify", "apply - verify", "approved"}
    blockers: list[str] = []
    evidence: list[str] = []
    if not approved:
        return ApplicationResult(job_id, url, detect_platform(url), "blocked", 0, False, False, [], ["Career OS has not approved this application."])
    if not url:
        return ApplicationResult(job_id, url, "unknown", "blocked", 0, False, False, [], ["Application URL is missing."])
    if not Path(resume_path).is_file():
        return ApplicationResult(job_id, url, detect_platform(url), "blocked", 0, False, False, [], ["Job-specific resume artifact is missing."])

    with sync_playwright() as p:
        browser = None
        cdp_url = os.environ.get("APPLICATION_BROWSER_CDP_URL", "").strip()
        if cdp_url:
            browser = p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
        else:
            profile_dir = os.environ.get("APPLICATION_BROWSER_PROFILE", str(ROOT / ".career-os" / "browser-profile"))
            context = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        title = page.title().casefold()
        body = page.locator("body").inner_text(timeout=15000).casefold()
        if any(token in body for token in ("captcha", "verify you are human", "security check")):
            blockers.append("Human/security verification is present; automation paused.")
        if any(token in body for token in ("job is no longer available", "position has been filled", "this job has expired")):
            blockers.append("Application page indicates the job is no longer available.")

        filled = 0
        if not blockers:
            inputs = page.locator("input, textarea").all()
            for field in inputs:
                input_type = (field.get_attribute("type") or "text").casefold()
                if input_type in {"hidden", "submit", "button", "file", "checkbox", "radio"}:
                    continue
                value = _field_value(_label_for_input(field), profile)
                if value is None:
                    continue
                try:
                    field.fill(value)
                    filled += 1
                except Exception:
                    blockers.append(f"Could not safely fill field: {_label_for_input(field)[:120]}")
                    break

            file_inputs = page.locator('input[type="file"]').all()
            if file_inputs:
                try:
                    file_inputs[0].set_input_files(resume_path)
                    resume_uploaded = True
                except Exception as exc:
                    resume_uploaded = False
                    blockers.append(f"Resume upload failed: {type(exc).__name__}")
            else:
                resume_uploaded = False
                blockers.append("No resume upload control was detected.")
        else:
            resume_uploaded = False

        # Never click an ambiguous submit control. Only a clear final-application
        # control is eligible, and every unknown question blocks submission.
        unknown_questions = []
        for locator in page.locator("input, textarea, select").all():
            if (locator.get_attribute("type") or "").casefold() in {"hidden", "file"}:
                continue
            label = _label_for_input(locator)
            if label and _field_value(label, profile) is None and not locator.is_disabled():
                unknown_questions.append(label[:120])
        if unknown_questions:
            blockers.append("Unknown application fields require verified answers: " + ", ".join(unknown_questions[:8]))

        if blockers:
            state = "paused"
            submitted = False
        else:
            buttons = page.locator("button, input[type='submit']").all()
            submitter = None
            for button in buttons:
                text = _norm(button.inner_text() if button.evaluate("el => el.tagName") == "BUTTON" else (button.get_attribute("value") or ""))
                if any(token in text for token in ("submit application", "submit application now", "apply now")):
                    submitter = button
                    break
            if submitter is None:
                state = "paused"
                submitted = False
                blockers.append("No unambiguous final-application control was detected.")
            else:
                submitter.click()
                page.wait_for_timeout(1500)
                confirmation = page.locator("body").inner_text(timeout=10000).casefold()
                submitted = any(token in confirmation for token in ("application submitted", "thanks for applying", "application received", "successfully applied"))
                state = "submitted" if submitted else "submitted_unverified"
                evidence.append(page.url)
                if not submitted:
                    blockers.append("Submit action occurred, but no authoritative confirmation text was observed.")

        try:
            evidence.append(f"page_title:{title[:200]}")
        except Exception:
            pass
        if cdp_url and browser:
            browser.close()
        else:
            context.close()

    return ApplicationResult(job_id, url, detect_platform(url), state, filled, resume_uploaded, submitted, evidence, blockers)


def main() -> int:
    job_file = os.environ.get("APPLICATION_JOB_FILE", "").strip()
    profile_file = os.environ.get("APPLICATION_PROFILE_FILE", "candidate/source_of_truth.json")
    resume_file = os.environ.get("APPLICATION_RESUME_FILE", "")
    if not job_file or not resume_file:
        raise SystemExit("APPLICATION_JOB_FILE and APPLICATION_RESUME_FILE are required")
    result = run_application(_load_json(job_file), _load_json(profile_file), resume_file)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.state in {"submitted", "paused", "submitted_unverified"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
