---
name: jd-intelligence
description: Analyze a job description into structured responsibilities, requirements, skills, seniority, constraints, and evidence needs for downstream career decisions.
---

# JD Intelligence

Use this skill when a job description needs structured analysis.

## Workflow
1. Preserve the source JD and provenance.
2. Segment the posting using known responsibility, required-qualification, and preferred-qualification heading variants.
3. Extract responsibilities, must-have requirements, preferred requirements, tools, domain terms, seniority, location, work model, and stated compensation.
4. Normalize known skill aliases into canonical skill names while preserving exact source wording in the source JD and extracted bullets.
5. Separate explicit requirements from inferred signals.
6. Mark ambiguous or missing information instead of guessing.
7. Produce a normalized analysis consumable by Fit Scorer, Resume Tailor, and ATS Auditor.

## Rules
- Never convert a preference into a hard requirement without evidence.
- Never treat a substring match as proof of a skill; use bounded/alias-aware matching.
- Keep exact source wording available for auditability.
- Keep deterministic extraction and normalization outside model prompts where practical.
