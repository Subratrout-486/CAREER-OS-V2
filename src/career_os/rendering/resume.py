from __future__ import annotations

from html import escape

from career_os.models.resume import TailoredResume


class ResumeRenderer:
    """Deterministically render an approved TailoredResume as ATS-safe HTML."""

    def render(self, resume: TailoredResume) -> str:
        summary = escape(resume.summary)
        bullets = "\n".join(f"<li>{escape(bullet.text)}</li>" for bullet in resume.bullets)
        keywords = "\n".join(f"<li>{escape(keyword)}</li>" for keyword in resume.matched_keywords)
        keyword_section = (
            f'<section aria-labelledby="keywords"><h2 id="keywords">Skills</h2><ul>{keywords}</ul></section>'
            if keywords
            else ""
        )
        return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resume</title>
<style>
@page {{ size: A4; margin: 14mm 16mm; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ font-family: Arial, Helvetica, sans-serif; color: #111; background: #fff; font-size: 10.5pt; line-height: 1.35; }}
main {{ max-width: 178mm; margin: 0 auto; }}
h1, h2 {{ page-break-after: avoid; }}
h1 {{ font-size: 18pt; margin: 0 0 6mm; }}
h2 {{ font-size: 11.5pt; margin: 5mm 0 2mm; border-bottom: 0.4pt solid #888; padding-bottom: 1mm; }}
p {{ margin: 0; }}
ul {{ margin: 0; padding-left: 5mm; }}
li {{ margin: 0 0 1.5mm; break-inside: avoid; }}
section {{ break-inside: avoid; }}
</style>
</head>
<body>
<main>
<h1>Resume</h1>
<section aria-labelledby="summary"><h2 id="summary">Summary</h2><p>{summary}</p></section>
<section aria-labelledby="experience"><h2 id="experience">Experience</h2><ul>{bullets}</ul></section>
{keyword_section}
</main>
</body>
</html>'''


def render_resume_html(resume: TailoredResume) -> str:
    return ResumeRenderer().render(resume)
