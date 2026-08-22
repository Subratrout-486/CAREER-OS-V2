---
name: job-scout
description: Discover current jobs from configured company and ATS sources, normalize them, reject duplicates and likely ghost jobs, and produce evidence-backed job intake records.
---

# Job Scout

Use this skill when finding or refreshing job opportunities.

## Workflow
1. Query only configured public sources and preserve the original source URL.
2. Normalize title, company, location, employment type, posted date, description, and application URL.
3. Deduplicate using stable external IDs first, then canonical URLs, then conservative content similarity.
4. Flag likely ghost jobs when freshness, source availability, or posting evidence is inconsistent; do not silently delete uncertain records.
5. Emit a structured intake record with provenance, duplicate status, and evidence signals.

## Rules
- Never invent a job, employer, posting date, salary, or application URL.
- A source failure is isolated to that source and must be observable.
- Keep deterministic normalization and duplicate decisions outside the model.
- Use explicit deduplication terminology and preserve the distinction between NEW, VERIFIED, GHOST, and DUPLICATE records.
