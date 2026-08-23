---
name: ats-audit
description: Audit a resume against a target job for ATS readability, requirement coverage, keyword alignment, formatting risks, unsupported claims, and page-composition quality.
---

# ATS Auditor

Use this skill before a resume is submitted or finalized.

## Workflow
1. Parse the resume into a normalized structure.
2. Compare it with the structured JD requirements.
3. Check section structure, dates, headings, keyword coverage, and likely parser hazards.
4. Normalize only bounded, deterministic skill aliases such as PowerBI/Power BI and RESTful APIs/REST API.
5. Identify missing high-value requirements and unsupported claims.
6. Check page count, measured page geometry, text preservation, and visual/page-composition findings supplied by Resume Rendering.
7. Distinguish substantive qualification gaps from presentation failures such as underfill, overflow, clipping, or cramped typography.
8. Produce actionable findings with severity and evidence.

## Page-composition audit
- `UNDERFILL`: one-page output has materially excessive unused space and relevant supported evidence was omitted.
- `OVERFLOW`: content exceeds one page or crosses the approved printable bounds.
- `CRAMPED`: content technically fits but violates approved readability/typography bounds or creates poor visual hierarchy.
- `PASS`: page is substantively filled, readable, parser-safe, and within approved geometry.
- Do not treat page-fill as a keyword-density target; filler is a failure.
- Do not silently accept a sparse resume merely because it is one page.

## Rules
- ATS optimization must not introduce false claims.
- Separate parser/format risks from substantive qualification gaps.
- Missing must-have requirements are errors; preferred/coverage gaps are warnings.
- Preserve provenance warnings separately from qualification findings.
- Do not use semantic similarity to override explicit evidence or hard requirements.
- A resume is not final until content, ATS, and page-composition gates pass.
