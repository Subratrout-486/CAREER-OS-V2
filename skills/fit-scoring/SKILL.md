---
name: fit-scoring
description: Score candidate-to-job fit using explicit JD requirements, verified candidate evidence, and transparent weighted criteria.
---

# Fit Scorer

Use this skill when ranking a candidate against a specific job.

## Workflow
1. Start from structured JD requirements and evidence records.
2. Score hard requirements separately from transferable or preferred signals.
3. Penalize missing critical evidence rather than assuming it exists.
4. Produce component scores, decisive gaps, supporting evidence, and confidence.
5. Keep the scoring formula deterministic and explainable; use models only for bounded interpretation.

## Rules
- Do not claim a fit that contradicts a hard requirement.
- A score must be traceable to requirements and evidence.
