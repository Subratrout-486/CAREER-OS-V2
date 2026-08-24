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
_MAX_RESUME_PAGES = 2


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_") or "Target_Role"


def resume_filename(candidate_name: str, target_role: str) -> str:
    filename = f"{_slug(candidate_name)}_{_slug(target_role)}.pdf"
    if any(marker in filename.casefold() for marker in _INTERNAL_MARKERS):
        raise ValueError("internal Career OS branding must not appear in resume filename")
    return filename


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _claim_lookup(profile: Mapping[str, object]) -> dict[str, tuple[str, str, str]]:
    lookup: dict[str, tuple[str, str, str]] = {}
    for experience in profile.get("experience", []):
        if not isinstance(experience, Mapping):
            continue
        company = str(experience.get("company", ""))
        for index, responsibility in enumerate(experience.get("responsibilities", [])):
            lookup[f"exp-{company.casefold().replace(' ', '-')}-{index}"] = ("experience", company, str(responsibility))
    for project in profile.get("projects", []):
        if not isinstance(project, Mapping):
            continue
        name = str(project.get("name", ""))
        for index, detail in enumerate(project.get("details", [])):
            lookup[f"project-{name.casefold().replace(' ', '-')}-{index}"] = ("project", name, str(detail))
    return lookup


def _selected(profile: Mapping[str, object], tailored: TailoredResume, section: str) -> dict[str, list[str]]:
    lookup = _claim_lookup(profile)
    grouped: dict[str, list[str]] = {}
    for bullet in tailored.bullets:
        for claim_id in bullet.evidence_claim_ids:
            entry = lookup.get(claim_id)
            if entry and entry[0] == section:
                grouped.setdefault(entry[1], []).append(entry[2])
                break
    return {key: list(dict.fromkeys(values)) for key, values in grouped.items()}


def render_resume_html(profile: Mapping[str, object], tailored: TailoredResume, *, target_role: str) -> str:
    candidate = profile.get("candidate", {})
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate profile is missing")
    name = str(candidate.get("name", "")).strip()
    if not name:
        raise ValueError("candidate name is required")
    location = str(candidate.get("location", "")).strip()
    headline = str(candidate.get("headline", "")).strip()
    experience = _selected(profile, tailored, "experience")
    projects = _selected(profile, tailored, "project")
    skills = profile.get("skills_and_tools", {})
    all_skills: list[str] = []
    if isinstance(skills, Mapping):
        for values in skills.values():
            if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                all_skills.extend(str(value) for value in values)
    matched = {item.casefold() for item in tailored.matched_keywords}
    relevant_skills = [skill for skill in all_skills if skill.casefold() in matched]
    for skill in all_skills:
        if skill not in relevant_skills and len(relevant_skills) < 18:
            relevant_skills.append(skill)

    css = (
        "@page { size: A4; margin: 11mm 13mm; }"
        "* { box-sizing: border-box; }"
        "body { margin:0; color:#111; background:#fff; font-family:Arial,Helvetica,sans-serif; font-size:9.4pt; line-height:1.24; }"
        "h1 { margin:0; font-size:20pt; line-height:1.05; }"
        "h2 { margin:9px 0 4px; padding-bottom:2px; border-bottom:1px solid #777; font-size:10.2pt; letter-spacing:.5px; text-transform:uppercase; }"
        "h3 { margin:5px 0 1px; font-size:9.8pt; } p { margin:2px 0 4px; }"
        "ul { margin:2px 0 4px 15px; padding:0; } li { margin:1.5px 0; }"
        ".header { margin-bottom:5px; } .contact { margin-top:2px; font-size:8.8pt; }"
        ".role { display:flex; justify-content:space-between; gap:8px; } .meta { white-space:nowrap; font-size:8.8pt; }"
        ".skills { font-size:8.8pt; } .section { break-inside:avoid; }"
    )
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>{_esc(name)} — {_esc(target_role)}</title><style>{css}</style></head><body>",
        f"<header class='header'><h1>{_esc(name)}</h1><div class='contact'>{_esc(location)} · {_esc(target_role)}</div><div class='contact'>{_esc(headline)}</div></header>",
        f"<section class='section'><h2>Professional Summary</h2><p>{_esc(tailored.summary)}</p></section>",
    ]
    if experience:
        parts.append("<section class='section'><h2>Experience</h2>")
        for item in profile.get("experience", []):
            if not isinstance(item, Mapping):
                continue
            company = str(item.get("company", ""))
            if company not in experience:
                continue
            parts.append(f"<div class='role'><strong>{_esc(company)} — {_esc(item.get('title', ''))}</strong><span class='meta'>{_esc(item.get('dates', ''))}</span></div>")
            parts.append("<ul>" + "".join(f"<li>{_esc(text)}</li>" for text in experience[company]) + "</ul>")
        parts.append("</section>")
    if projects:
        parts.append("<section class='section'><h2>Projects</h2>")
        for project in profile.get("projects", []):
            if not isinstance(project, Mapping):
                continue
            project_name = str(project.get("name", ""))
            if project_name in projects:
                parts.append(f"<h3>{_esc(project_name)}</h3><ul>" + "".join(f"<li>{_esc(text)}</li>" for text in projects[project_name]) + "</ul>")
        parts.append("</section>")
    if relevant_skills:
        parts.append(f"<section class='section'><h2>Skills &amp; Tools</h2><p class='skills'>{_esc(' · '.join(dict.fromkeys(relevant_skills)))}</p></section>")
    education = profile.get("education", [])
    if isinstance(education, Sequence) and not isinstance(education, (str, bytes)) and education:
        parts.append("<section class='section'><h2>Education</h2>")
        for item in education:
            if isinstance(item, Mapping):
                parts.append(f"<div class='role'><strong>{_esc(item.get('qualification', ''))}</strong><span class='meta'>{_esc(item.get('dates', ''))}</span></div><p>{_esc(item.get('institution', ''))}</p>")
        parts.append("</section>")
    result = "".join(parts) + "</body></html>"
    if any(marker in result.casefold() for marker in _INTERNAL_MARKERS):
        raise ValueError("internal Career OS branding leaked into candidate-facing resume")
    return result


def render_resume_pdf(html_content: str, output_path: Path) -> None:
    from playwright.sync_api import sync_playwright
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="load")
        page.pdf(path=str(output_path), format="A4", print_background=True, prefer_css_page_size=True)
        browser.close()


def validate_resume_pdf(pdf_path: Path, candidate_name: str) -> dict[str, object]:
    """Validate a candidate PDF while allowing the agreed 1–2 page range."""
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    if not 1 <= page_count <= _MAX_RESUME_PAGES:
        raise ValueError(f"resume must be between one and two pages; found {page_count}")

    extracted_pages: list[str] = []
    for page in reader.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if abs(width - _A4_WIDTH_POINTS) > _A4_TOLERANCE_POINTS or abs(height - _A4_HEIGHT_POINTS) > _A4_TOLERANCE_POINTS:
            raise ValueError(f"resume page is not A4: {width:.2f} x {height:.2f} points")
        extracted_pages.append(page.extract_text() or "")

    text = "\n".join(extracted_pages)
    if candidate_name not in text:
        raise ValueError("resume PDF does not contain the canonical candidate name")
    if any(marker in text.casefold() for marker in _INTERNAL_MARKERS):
        raise ValueError("internal Career OS branding leaked into rendered resume PDF")
    return {
        "page_count": page_count,
        "page_limit": _MAX_RESUME_PAGES,
        "page_width_points": float(reader.pages[0].mediabox.width),
        "page_height_points": float(reader.pages[0].mediabox.height),
        "text_length": len(text),
    }
