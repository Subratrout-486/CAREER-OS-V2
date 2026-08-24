from __future__ import annotations

from career_os.models.resume import ResumeBullet, TailoredResume
from career_os.resume_artifact import render_resume_html, resume_filename


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


def test_resume_filename_is_candidate_facing() -> None:
    assert resume_filename("Subrat Rout", "Product Support Rep I") == "Subrat_Rout_Product_Support_Rep_I.pdf"
    assert "career_os" not in resume_filename("Subrat Rout", "Product Support Rep I").casefold()


def test_resume_html_contains_selected_evidence_and_no_internal_branding() -> None:
    tailored = TailoredResume(
        summary="Production support engineer.",
        bullets=(ResumeBullet("L2 production support for enterprise applications", ("exp-factset-systems-0",)),),
        matched_keywords=("python", "sql"),
    )
    document = render_resume_html(_profile(), tailored, target_role="Product Support Rep I")
    lowered = document.casefold()
    assert "subrat rout" in lowered
    assert "l2 production support" in lowered
    assert "north orissa university" in lowered
    assert "career os v2" not in lowered
    assert "career-os-v2" not in lowered
