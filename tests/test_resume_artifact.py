from __future__ import annotations

from pathlib import Path

import pypdf
import playwright.sync_api

from career_os import resume_artifact
from career_os.models.resume import ResumeBullet, TailoredResume
from career_os.resume_artifact import (
    render_resume_html,
    render_resume_pdf,
    resume_filename,
    validate_resume_pdf,
)


def _profile() -> dict[str, object]:
    return {
        "candidate": {
            "name": "Subrat Rout",
            "location": "Hyderabad, India",
            "headline": "Support Engineer | Production Support | Python | AWS",
        },
        "experience": [
            {
                "company": "FactSet Systems",
                "title": "Product Support Engineer",
                "dates": "Nov 2024 – Jan 2026",
                "responsibilities": ["L2 production support for enterprise applications"],
            }
        ],
        "projects": [],
        "skills_and_tools": {"professional_experience": ["Python", "Oracle", "SQL"]},
        "education": [
            {"qualification": "Bachelor of Commerce", "institution": "North Orissa University", "dates": "2018 – 2021"}
        ],
    }


def _tailored() -> TailoredResume:
    return TailoredResume(
        summary="Production support engineer.",
        bullets=(ResumeBullet("L2 production support for enterprise applications", ("exp-factset-systems-0",)),),
        matched_keywords=("python", "sql"),
    )


def test_resume_filename_is_candidate_facing() -> None:
    assert resume_filename("Subrat Rout", "Product Support Rep I") == "Subrat_Rout_Product_Support_Rep_I.pdf"
    assert "career_os" not in resume_filename("Subrat Rout", "Product Support Rep I").casefold()


def test_resume_html_contains_selected_evidence_and_no_internal_branding() -> None:
    document = render_resume_html(_profile(), _tailored(), target_role="Product Support Rep I")
    lowered = document.casefold()
    assert "subrat rout" in lowered
    assert "l2 production support" in lowered
    assert "north orissa university" in lowered
    assert "@page { size: a4;" in lowered
    assert "career os v2" not in lowered
    assert "career-os-v2" not in lowered


def test_resume_pdf_is_one_page_a4_and_machine_readable(tmp_path) -> None:
    html = render_resume_html(_profile(), _tailored(), target_role="Product Support Rep I")
    output = tmp_path / "Subrat_Rout_Product_Support_Rep_I.pdf"
    render_resume_pdf(html, output)
    result = validate_resume_pdf(output, "Subrat Rout")
    assert result["page_count"] == 1
    assert abs(float(result["page_width_points"]) - 595.28) < 2
    assert abs(float(result["page_height_points"]) - 841.89) < 2
    assert int(result["text_length"]) > 100


def test_render_resume_pdf_adapts_scale_until_one_page(monkeypatch, tmp_path: Path):
    scales: list[float] = []

    class FakePage:
        def set_content(self, html: str, wait_until: str):
            assert html
            assert wait_until == "load"

        def pdf(self, *, path: str, format: str, print_background: bool, prefer_css_page_size: bool, scale: float):
            assert format == "A4"
            assert print_background is True
            assert prefer_css_page_size is True
            scales.append(scale)
            Path(path).write_bytes(b"synthetic-pdf")

    class FakeBrowser:
        def new_page(self):
            return FakePage()

        def close(self):
            pass

    class FakeChromium:
        def launch(self):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_pdf_reader(path: str):
        count = 2 if len(scales) < 3 else 1
        return type("Reader", (), {"pages": [object()] * count})()

    monkeypatch.setattr(playwright.sync_api, "sync_playwright", lambda: FakePlaywright())
    monkeypatch.setattr(pypdf, "PdfReader", fake_pdf_reader)

    output = tmp_path / "resume.pdf"
    resume_artifact.render_resume_pdf("<html><body>resume</body></html>", output)

    assert scales == [1.0, 0.95, 0.9]
    assert output.exists()


def test_single_page_scale_contract_has_readable_floor():
    assert resume_artifact._SINGLE_PAGE_SCALES[0] == 1.0
    assert resume_artifact._SINGLE_PAGE_SCALES[-1] >= 0.75
