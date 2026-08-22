from career_os.agents.resume_renderer import ResumeRenderer
from career_os.models.resume import ResumeBullet, TailoredResume


def _resume() -> TailoredResume:
    return TailoredResume(
        summary="Technical support professional with evidence-backed experience.",
        bullets=(
            ResumeBullet("Troubleshot SQL production issues", ("c1",)),
            ResumeBullet("Built PowerBI dashboards", ("c2",)),
        ),
        matched_keywords=("power bi", "sql"),
        omitted_claim_ids=("c3",),
        edit_trace=("Reordered evidence-backed bullets by JD relevance.",),
    )


def test_resume_renderer_produces_semantic_ats_safe_html() -> None:
    html = ResumeRenderer().render_html(_resume(), title="Target Resume")

    assert html.startswith("<!doctype html>")
    assert '<main>' in html
    assert '<h1>Target Resume</h1>' in html
    assert '<h2 id="summary-heading">Summary</h2>' in html
    assert '<h2 id="experience-heading">Experience</h2>' in html
    assert '<ul>' in html
    assert '<li>Troubleshot SQL production issues</li>' in html
    assert '<li>Built PowerBI dashboards</li>' in html


def test_resume_renderer_escapes_resume_content() -> None:
    resume = TailoredResume(
        summary='<script>alert("x")</script>',
        bullets=(ResumeBullet('Used <unsafe> & "quoted" text', ("c1",)),),
    )

    html = ResumeRenderer().render_html(resume)

    assert '<script>' not in html
    assert '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in html
    assert 'Used &lt;unsafe&gt; &amp; &quot;quoted&quot; text' in html


def test_resume_renderer_uses_single_column_print_layout() -> None:
    html = ResumeRenderer().render_html(_resume())

    assert '@page { size: A4;' in html
    assert 'max-width: 180mm' in html
    assert 'display: grid' not in html
    assert 'columns:' not in html
    assert 'position: absolute' not in html
