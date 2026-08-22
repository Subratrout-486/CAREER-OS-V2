from pathlib import Path

from career_os.models.resume import ResumeBullet, TailoredResume
from career_os.rendering import PDFRenderer, ResumeRenderer, validate_pdf


def sample_resume() -> TailoredResume:
    return TailoredResume(
        summary="Research analyst with experience in data validation.",
        bullets=(
            ResumeBullet("Investigated SQL data issues and documented root causes.", ("claim-1",)),
            ResumeBullet("Validated Power BI reporting outputs against source data.", ("claim-2",)),
        ),
        matched_keywords=("SQL", "Power BI"),
    )


def test_resume_renderer_is_semantic_and_escapes_text():
    resume = TailoredResume(
        summary="Analyst <trusted>",
        bullets=(ResumeBullet("Built <safe> reports", ("c1",)),),
    )
    html = ResumeRenderer().render(resume)

    assert '<main>' in html
    assert '<section aria-labelledby="summary">' in html
    assert '<section aria-labelledby="experience">' in html
    assert '<li>Built &lt;safe&gt; reports</li>' in html
    assert '<script' not in html.lower()
    assert '@page { size: A4;' in html


def test_pdf_renderer_produces_valid_a4_pdf(tmp_path: Path):
    resume = sample_resume()
    html = ResumeRenderer().render(resume)
    output = tmp_path / "resume.pdf"

    PDFRenderer().render_html(html, output)
    pdf_bytes = output.read_bytes()
    validate_pdf(pdf_bytes, expected_text=(resume.summary, "SQL", "Power BI"))

    assert output.exists()
    assert output.stat().st_size > 500
