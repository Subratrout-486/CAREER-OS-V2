---
name: resume-rendering
description: Render a tailored resume into deterministic, ATS-readable output while preserving source text, evidence boundaries, and print-safe structure.
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
7. Verify the rendered structure before any PDF conversion or submission.

## Rules
- Never add content during rendering.
- Never use images, text baked into graphics, tables, or multi-column layout in the ATS-safe default template.
- Keep rendering deterministic and dependency-light.
- Treat PDF/browser conversion as a separate infrastructure boundary; never report a PDF as verified unless the converter actually ran successfully.
