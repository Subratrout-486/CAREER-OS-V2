from __future__ import annotations

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


def test_resume_pdf_accepts_two_pages_when_content_requires_it(tmp_path) -> None:
    profile = _profile()
    responsibilities = [
        f"Supported enterprise workforce management workflow {i}: investigated incidents, validated data, coordinated resolution, and documented the result."
        for i in range(1, 26)
    ]
    profile["experience"] = [
        {
            "company": "FactSet Systems",
            "title": "Product Support Engineer",
            "dates": "Nov 2024 – Jan 2026",
            "responsibilities": responsibilities,
        }
    ]
    bullets = tuple(ResumeBullet(text, (f"exp-factset-systems-{i}",)) for i, text in enumerate(responsibilities))
    tailored = TailoredResume(summary="Production support engineer.", bullets=bullets, matched_keywords=("sql",))
    html = render_resume_html(profile, tailored, target_role="Product Support Engineer")
    output = tmp_path / "Subrat_Rout_Product_Support_Engineer.pdf"
    render_resume_pdf(html, output)
    result = validate_resume_pdf(output, "Subrat Rout")
    assert result["page_count"] == 2
    assert abs(float(result["page_width_points"]) - 595.28) < 2
    assert abs(float(result["page_height_points"]) - 841.89) < 2
    assert int(result["text_length"]) > 100
