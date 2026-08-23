#!/usr/bin/env python3
"""Provider-free smoke test for one real public job posting."""
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from career_os.candidate_profile import load_candidate_source_of_truth
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceSource, SupportStatus
from career_os.models.resume import ResumeBullet, ResumeProfile
from career_os.pipeline import CareerPipeline


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.json_ld: list[str] = []
        self.meta: dict[str, str] = {}
        self._script_type = ""
        self._in_script = False
        self._title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag == "script":
            self._in_script = True
            self._script_type = (attrs_map.get("type") or "").casefold()
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = attrs_map.get("property") or attrs_map.get("name")
            value = attrs_map.get("content")
            if key and value:
                self.meta[key.casefold()] = value.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False
            self._script_type = ""
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_script and "ld+json" in self._script_type:
            self.json_ld.append(data)
        elif self._in_title:
            self._title += data
        elif not self._in_script:
            cleaned = " ".join(data.split())
            if cleaned:
                self.parts.append(cleaned)


def _fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Career-OS-V2-native-smoke/1.1", "Accept": "text/html,application/xhtml+xml"})
    with urlopen(request, timeout=25) as response:
        return response.read(8_000_000).decode("utf-8", errors="replace")


def _job_posting(parser: _HTMLText) -> dict[str, object]:
    for raw in parser.json_ld:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = value if isinstance(value, list) else [value]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            types = item.get("@type", [])
            if types == "JobPosting" or "JobPosting" in (types if isinstance(types, list) else []):
                return item
    return {}


def _location(value: object) -> str | None:
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            bits = [address.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
            return ", ".join(str(x) for x in bits if x)
        name = value.get("name")
        return str(name) if name else None
    if isinstance(value, list):
        values = [_location(item) for item in value]
        return "; ".join(x for x in values if x) or None
    return None


def _company(posting: dict[str, object], parser: _HTMLText, source_url: str, title: str) -> str | None:
    org = posting.get("hiringOrganization")
    if isinstance(org, dict) and org.get("name"):
        return str(org["name"]).strip()
    for key in ("og:site_name", "application-name", "author"):
        if parser.meta.get(key):
            return parser.meta[key]
    # SAP/SuccessFactors pages frequently put the employer in the HTML title even
    # when JobPosting JSON-LD omits hiringOrganization.
    if " | " in title:
        suffix = title.rsplit(" | ", 1)[-1].strip()
        if suffix and "job details" not in suffix.casefold():
            return suffix
    host = urlparse(source_url).hostname or ""
    if host.startswith("careers."):
        host = host[len("careers."):]
    label = host.split(".", 1)[0].replace("-", " ").strip()
    return label.title() or None


def _claims(profile: dict[str, object]) -> tuple[list[EvidenceClaim], ResumeProfile]:
    source = EvidenceSource("candidate/source_of_truth.json", "candidate_source_of_truth", "Canonical candidate Source of Truth")
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

    # Education and the canonical skill inventory are evidence too. They are not
    # employment claims, but excluding them causes valid degree/skill requirements
    # to be falsely classified as hard gaps.
    for index, education in enumerate(profile.get("education", [])):
        qualification = str(education.get("qualification", ""))
        institution = str(education.get("institution", ""))
        claim_id = f"education-{index}"
        claim = f"Education: {qualification} — {institution}"
        claims.append(EvidenceClaim(claim_id, claim, EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source))

    skills = profile.get("skills_and_tools", {})
    for category, values in skills.items():
        for index, skill in enumerate(values if isinstance(values, list) else []):
            claim_id = f"skill-{category}-{index}"
            claim = f"{category}: {skill}"
            claims.append(EvidenceClaim(claim_id, claim, EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source))

    summary = str(profile["candidate"]["professional_summary"])
    return claims, ResumeProfile(summary=summary, bullets=tuple(bullets))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://careers.brightstarlottery.com/job/Hyderabad-Product-Support-Rep-I-500-081/1420303333/")
    parser.add_argument("--output", default=".career-os/native-smoke-result.json")
    args = parser.parse_args()

    html = _fetch(args.url)
    parser_html = _HTMLText()
    parser_html.feed(html)
    posting = _job_posting(parser_html)

    title = str(posting.get("title") or parser_html._title.strip())
    description = str(posting.get("description") or "\n".join(parser_html.parts))
    company = _company(posting, parser_html, args.url, title)
    location = _location(posting.get("jobLocation"))
    if not location:
        match = re.search(r"Hyderabad[^\n]{0,80}", "\n".join(parser_html.parts), re.I)
        location = match.group(0).strip() if match else None
    if not title or not description:
        raise RuntimeError("Could not extract a usable title and job description from the public posting")

    profile = load_candidate_source_of_truth()
    claims, resume = _claims(profile)
    raw_job = {"company": company or "Unknown employer", "title": title, "location": location, "source_url": args.url, "source": "official career page", "description": description, "posted_at": posting.get("datePosted") or posting.get("dateModified")}

    run_id = "native-smoke-" + re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:70]
    pipeline = CareerPipeline(Path(".career-os/native-smoke-checkpoint.json"))
    result = pipeline.run(run_id=run_id, raw_job=raw_job, resume=resume, claims=claims)

    output = {
        "run_id": run_id,
        "source_url": args.url,
        "company": result.job.company,
        "title": result.job.title,
        "location": result.job.location,
        "application_ready": result.application_ready,
        "completed_stages": result.checkpoint.completed_stages,
        "fit": result.fit.__dict__,
        "matched_keywords": list(result.tailored_resume.matched_keywords),
        "ats_findings": [finding.__dict__ for finding in result.ats_audit.findings],
        "recruiter_recommendation": result.recruiter_review.recommendation,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
