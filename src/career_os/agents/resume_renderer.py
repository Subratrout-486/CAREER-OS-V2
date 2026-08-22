from __future__ import annotations

from html import escape

from career_os.models.resume import TailoredResume


class ResumeRenderer:
    """Render a tailored resume as semantic, ATS-readable HTML.

    The renderer is deliberately deterministic and dependency-free. It uses a
    single-column document flow, semantic headings, real lists, selectable text,
    and print CSS for A4 output. PDF conversion is kept outside this module so
    rendering remains testable without a browser or system converter.
    """

    name = "resume_renderer"

    def render_html(self, resume: TailoredResume, *, title: str = "Resume") -> str:
        summary = escape(resume.summary.strip())
        bullets = "\n".join(
            f"      <li>{escape(bullet.text.strip())}</li>"
            for bullet in resume.bullets
            if bullet.text.strip()
        )

        summary_section = (
            f"\n    <section aria-labelledby=\"summary-heading\">\n"
            f"      <h2 id=\"summary-heading\">Summary</h2>\n"
            f"      <p>{summary}</p>\n"
            f"    </section>"
            if summary
            else ""
        )
        bullets_section = (
            f"\n    <section aria-labelledby=\"experience-heading\">\n"
            f"      <h2 id=\"experience-heading\">Experience</h2>\n"
            f"      <ul>\n{bullets}\n      </ul>\n"
            f"    </section>"
            if bullets
            else ""
        )

        safe_title = escape(title.strip() or "Resume")
        return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    @page {{ size: A4; margin: 16mm 15mm; }}
    :root {{ color-scheme: light; }}
    body {{
      margin: 0 auto;
      max-width: 180mm;
      color: #111;
      background: #fff;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 10.5pt;
      line-height: 1.35;
    }}
    main {{ width: 100%; }}
    h1 {{ margin: 0 0 5mm; font-size: 20pt; line-height: 1.1; }}
    h2 {{ margin: 5mm 0 2mm; font-size: 11.5pt; text-transform: uppercase; letter-spacing: .04em; }}
    p {{ margin: 0; }}
    ul {{ margin: 0; padding-left: 5mm; }}
    li {{ margin: 0 0 1.5mm; break-inside: avoid; }}
    section {{ break-inside: avoid; }}
    @media print {{ body {{ max-width: none; }} }}
  </style>
</head>
<body>
  <main>
    <h1>{safe_title}</h1>{summary_section}{bullets_section}
  </main>
</body>
</html>'''


def render_resume_html(resume: TailoredResume, *, title: str = "Resume") -> str:
    return ResumeRenderer().render_html(resume, title=title)
