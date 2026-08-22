---
name: ats-audit
description: Audit a resume against a target job for ATS readability, requirement coverage, keyword alignment, formatting risks, and unsupported claims.
---

# ATS Auditor

Use this skill before a resume is submitted or finalized.

## Workflow
1. Parse the resume into a normalized structure.
2. Compare it with the structured JD requirements.
3. Check section structure, dates, headings, keyword coverage, and likely parser hazards.
4. Normalize only bounded, deterministic skill aliases such as PowerBI/Power BI and RESTful APIs/REST API.
5. Identify missing high-value requirements and unsupported claims.
6. Produce actionable findings with severity and evidence.

## Rules
- ATS optimization must not introduce false claims.
- Separate parser/format risks from substantive qualification gaps.
- Missing must-have requirements are errors; preferred/coverage gaps are warnings.
- Preserve provenance warnings separately from qualification findings.
- Do not use semantic similarity to override explicit evidence or hard requirements.
