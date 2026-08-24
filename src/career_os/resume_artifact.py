"""Candidate-facing resume artifact rendering.

The renderer is deliberately provider-free. It consumes the canonical candidate
profile plus the deterministic TailoredResume produced by ResumeTailor, renders
ATS-readable semantic HTML, and optionally prints that HTML to an A4 PDF with
Playwright. Internal Career OS identifiers are rejected from the final filename
and document body.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Mapping, Sequence

from career_os.models.resume import TailoredResume

_INTERNAL_MARKERS = ("career os v2", "career-os-v2", "career_os_v2")
_A4_WIDTH_POINTS = 595.28
_A4_HEIGHT_POINTS = 841.89
_A4_TOLERANCE_POINTS = 2.0


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    return value.strip("_") or "Target_Role"


def resume_filename(candidate_name: str, target_role: str) -> str:
    """Return the canonical candidate-facing PDF filename."""
    filename = f"{_slug(candidate_name)}_{_slug(target_role)}.pdf"
    if any(marker in filename.casefold() for marker in _INTERNAL_MARKERS):
        raise ValueError("internal Career OS branding must not appear in resume filename")
    return filename


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _claim_lookup(profile: Mapping[str, object]) -> dict[str, tuple[str, str, str]]:
    """Map evidence IDs to (section, employer/project, text)."""
    lookup: dict[str, tuple[str, str, str]] = {}
    for experience in profile.get("experience", []):
        if not isinstance(experience, Mapping):
            continue
        company = str(experience.get("company", ""))
        for index, responsibility in enumerate(experience.get("responsibilities", [])):
            lookup[f"exp-{company.casefold().replace(' ', '-')}-{index}"] = (
                "experience", company, str(responsibility)
            )
    for project in profile.get("projects", []):
        if not isinstance(project, Mapping):
            continue
        name = str(project.get("name", ""))
        for index, detail in enumerate(project.get("details", [])):
            lookup[f"project-{name.casefold().replace(' ', '-')}-{index}"] = (
                "project", name, str(detail)
            )
    return lookup


def _selected_experience(profile: Mapping[str, object], tailored: TailoredResume) -> dict[str, list[str]]:
    lookup = _claim_lookup(profile)
    grouped: dict[str, list[str]] = {}
    for bullet in tailored.bullets:
        for claim_id in bullet.evidence_claim_ids:
            entry = lookup.get(claim_id)
            if entry and entry[0] == "experience":
                grouped.setdefault(entry[1], []).append(entry[2])
                break
    for company, bullets in list(grouped.items()):
        grouped[company] = list(dict.fromkeys(bullets))
    return grouped


def _selected_projects(profile: Mapping[str, object], tailored: TailoredResume) -> dict[str, list[str]]:
    lookup = _claim_lookup(profile)
    grouped: dict[str, list[str]] = {}
    for bullet in tailored.bullets:
        for claim_id in bullet.evidence_claim_ids:
            entry = lookup.get(claim_id)
            if entry and entry[0] == "project":
                grouped.setdefault(entry[1], []).append(entry[2])
                break
    for project, bullets in list(grouped.items()):
        grouped[project] = list(dict.fromkeys(bullets))
    return grouped


def render_resume_html(
    profile: Mapping[str, object],
    tailored: TailoredResume,
    *,
    target_role: str,
) -> str:
    """Render a semantic, single-column, ATS-readable resume HTML document."""
    candidate = profile.get("candidate", {})
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate profile is missing")
    name = str(candidate.get("name", "")).strip()
    location = str(candidate.get("location", "")).strip()
    headline = str(candidate.get("headline", "")).strip()
    if not name:
        raise ValueError("candidate name is required")

    experience = _selected_experience(profile, tailored)
    projects = _selected_projects(profile, tailored)
    education = profile.get("education", [])
    skills = profile.get("skills_and_tools", {})
    relevant_skills: list[str] = []
    if isinstance(skills, Mapping):
        all_skills: list[str] = []
        for values in skills.values():
            if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                all_skills.extend(str(value) for value in values)
        matched = {item.casefold() for item in tailored.matched_keywords}
        relevant_skills = [skill for skill in all_skills if skill.casefold() in matched]
        for skill in all_skills:
            if skill not in relevant_skills and len(relevant_skills) < 18:
                relevant_skills.append(skill)

    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{_esc(name)} — {_esc(target_role)}</title>",
        """<style>
@page { size: A4; margin: 11mm 13mm; }
* { box-sizing: border-box; }
body { margin: 0; color: #111; background: #fff; font-family: Arial, Helvetica, sans-serif; font-size: 9.4pt; line-height: 1.24; }
h1 { margin: 0; font-size: 20pt; line-height: 1.05; letter-spacing: .2px; }
h2 { margin: 9px 0 4px; padding-bottom: 2px; border-bottom: 1px solid #777; font-size: 10.2pt; letter-spacing: .5px; text-transform: uppercase; }
h3 { margin: 5px 0 1px; font-size: 9.8pt; }
p { margin: 2px 0 4px; }
ul { margin: 2px 0 4px 15px; padding: 0; }
li { margin: 1.5px 0; }
.header { margin-bottom: 5px; }
.contact { margin-top: 2px; font-size: 8.8pt; }
.role { display: flex; justify-content: space-between; gap: 8px; }
.role strong { font-size: 9.8pt; }
.meta { white-space: nowrap; font-size: 8.8pt; }
.skills { font-size: 8.8pt; }
.section { break-inside: avoid; }
</style></head><body>",
        f'<header class="header"><h1>{_esc(name)}</h1>',
        f'<div class="contact">{_esc(location)} · {_esc(target_role)}</div>',
        f'<div class="contact">{_esc(headline)}</div></header>',
        '<section class="section"><h2>Professional Summary</h2>',
        f"<p>{_esc(tailored.summary)}</p></section>",
    ]

    if experience:
        parts.append('<section class="section"><h2>Experience</h2>')
        for item in profile.get("experience", []):
            if not isinstance(item, Mapping):
                continue
            company = str(item.get("company", ""))
            if company not in experience:
                continue
            parts.append(
                f'<div class="role"><strong>{_esc(company)} — {_esc(item.get("title", ""))}</strong>'
                f'<span class="meta">{_esc(item.get("dates", ""))}</span></div>'
            )
            parts.append("<ul>" + "".join(f"<li>{_esc(text)}</li>" for text in experience[company]) + "</ul>")
        parts.append("</section>")

    if projects:
        parts.append('<section class="section"><h2>Projects</h2>')
        for project in profile.get("projects", []):
            if not isinstance(project, Mapping):
                continue
            name_value = str(project.get("name", ""))
            if name_value not in projects:
                continue
            parts.append(f"<h3>{_esc(name_value)}</h3>")
            parts.append("<ul>" + "".join(f"<li>{_esc(text)}</li>" for text in projects[name_value]) + "</ul>")
        parts.append("</section>")

    if relevant_skills:
        parts.append('<section class="section"><h2>Skills &amp; Tools</h2>')
        parts.append(f'<p class="skills">{_esc(" · ".join(dict.fromkeys(relevant_skills)))}</p></section>')

    if isinstance(education, Sequence) and not isinstance(education, (str, bytes)) and education:
        parts.append('<section class="section"><h2>Education</h2>')
        for item in education:
            if not isinstance(item, Mapping):
                continue
            parts.append(
                f'<div class="role"><strong>{_esc(item.get("qualification", ""))}</strong>'
                f'<span class="meta">{_esc(item.get("dates", ""))}</span></div>'
                f'<p>{_esc(item.get("institution", ""))}</p>'
            )
        parts.append("</section>")

    result = "".join(parts) + "</body></html>"
    lowered = result.casefold()
    if any(marker in lowered for marker in _INTERNAL_MARKERS):
        raise ValueError("internal Career OS branding leaked into candidate-facing resume")
    return result


def render_resume_pdf(html_content: str, output_path: Path) -> None:
    """Print resume HTML to A4 PDF using the already-installed Playwright runtime."""
    from playwright.sync_api import sync_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="load")
        page.pdf(path=str(output_path), format="A4", print_background=True, prefer_css_page_size=True)
        browser.close()


def validate_resume_pdf(pdf_path: Path, candidate_name: str) -> dict[str, object]:
    """Validate the machine-readable contract of a generated candidate resume."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    if len(reader.pages) != 1:
        raise ValueError(f"resume must be exactly one page; found {len(reader.pages)}")
    page = reader.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    if abs(width - _A4_WIDTH_POINTS) > _A4_TOLERANCE_POINTS or abs(height - _A4_HEIGHT_POINTS) > _A4_TOLERANCE_POINTS:
        raise ValueError(f"resume page is not A4: {width:.2f} x {height:.2f} points")
    text = page.extract_text() or ""
    if candidate_name not in text:
        raise ValueError("resume PDF does not contain the canonical candidate name")
    lowered = text.casefold()
    if any(marker in lowered for marker in _INTERNAL_MARKERS):
        raise ValueError("internal Career OS branding leaked into rendered resume PDF")
    return {"page_count": 1, "page_width_points": width, "page_height_points": height, "text_length": len(text)}
