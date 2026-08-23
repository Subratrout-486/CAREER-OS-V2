---
name: resume-rendering
description: Render a tailored resume into deterministic, ATS-readable HTML and validated A4 PDF while preserving source text, evidence boundaries, print-safe structure, and balanced page utilization.
---

# Resume Rendering

Use this skill after resume tailoring and before application handoff.

## Workflow
1. Render only the approved TailoredResume content.
2. Preserve text exactly; rendering must never rewrite claims.
3. Use semantic HTML headings, paragraphs, and real lists.
4. Keep the default layout single-column and machine-readable.
5. Use A4 print CSS with predictable margins and page-break behavior.
6. Escape all user-controlled text before inserting it into HTML.
7. Verify the HTML structure before PDF conversion.
8. Convert HTML to PDF with Playwright-managed Chromium using A4 and CSS page-size preference.
9. Validate the resulting PDF for readability, A4 geometry, required text preservation, overflow, and page utilization.
10. Render a PNG preview at normal reading size for visual QA before finalizing.
11. If page utilization is materially underfilled, return a structured `UNDERFILL` finding to Resume Tailoring so it can recover supported evidence; do not add filler during rendering.
12. If content overflows or becomes cramped, return an `OVERFLOW` or `CRAMPED` finding so Resume Tailoring can reduce low-signal content before typography is reduced.

## Page-composition gate
- A one-page resume must be substantively filled while remaining readable; a large unused lower-page region is a failure when additional relevant supported evidence exists.
- Use measured PDF geometry rather than subjective word count alone.
- Treat page-fill thresholds as renderer calibration values, not universal resume rules; document the thresholds used by the implementation.
- Never compensate for underfill with repeated keywords, generic skills, or artificial spacing.
- Never compensate for overflow by shrinking below approved minimum typography or margins.
- Visual QA must check hierarchy, section rhythm, orphaned headings, clipping/collisions, and normal-size readability.

## Rules
- Never add content during rendering.
- Never use images, text baked into graphics, tables, or multi-column layout in the ATS-safe default template.
- Keep the canonical resume content independent from presentation output.
- Do not report a PDF as verified unless Chromium conversion and PDF validation both succeed.
- Treat browser installation as CI infrastructure, not an implicit local dependency.
