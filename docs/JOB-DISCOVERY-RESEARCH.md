# CareerOS V2 Job Discovery Research

## Goal
Feed real job listings into the existing deterministic Career OS pipeline so jobs found by external search workflows can be processed without inventing candidate facts.

## Existing V2 boundary
`CareerPipeline.run()` accepts a normalized `raw_job`, `ResumeProfile`, and evidence claims. `JobIntakePipeline` normalizes and deduplicates supplied job records. `JobScout` classifies sources and performs canonical/content/fuzzy deduplication.

V2 therefore already has the processing side, but it does not currently provide a production job-source discovery loop.

## Reusable public patterns researched

### career-ops
Open-source job-search system with zero-token scanning of 150+ company portals, including Greenhouse, Ashby and Lever. Its scanner uses structured ATS endpoints where available and filters before AI evaluation. This is the strongest reference for discovery architecture.

### career-ops-ui
Provides a browser UI over career-ops and exposes scan/dashboard APIs. It supports Greenhouse, Ashby, Lever, Workable, SmartRecruiters, Workday and additional regional portals, with deduplication and verification workflows.

### jobops
Self-hosted MCP server combining Greenhouse/Ashby/Lever/Workday polling, Playwright fallback, content-hash deduplication, batch evaluation and application tracking. Useful reference for source adapters and verification, but its application execution must not be copied into V2's core.

### go-job
MCP job search server exposing a unified search across multiple job sources. Useful as a source-abstraction reference, but source reliability and terms must be evaluated individually.

## Implementation principles

1. Prefer public structured ATS feeds over brittle scraping when available.
2. Keep source adapters separate from deterministic Career OS processing.
3. Normalize every source into the existing `JobRecord` model.
4. Deduplicate before expensive JD/AI processing.
5. Preserve source URL, source/provider and provenance.
6. Mark stale/uncertain listings rather than treating them as active.
7. Do not auto-submit applications.
8. Discovery should be usable without a paid API where a public source exists.
9. Provider failures must be explicit and never become successful pipeline completion.
10. External provider credentials must remain outside the deterministic pipeline core.

## Initial sources

The first adapter set should target public ATS/job-board feeds that can be queried without user credentials: Greenhouse, Ashby, Lever and Workable where publicly available. Additional sources should be added only after verifying a stable public interface and acceptable usage constraints.

## Processing contract

`discover -> normalize -> dedupe -> persist/return -> CareerPipeline.run`

The dashboard should consume the resulting canonical records rather than maintaining a second job database.

## Verification requirement

A discovery implementation is not complete until a real source response can be transformed into a `JobRecord`, deduplicated, passed through the V2 pipeline, and produce a checkpointed result. Fixtures/unit tests are necessary but not sufficient; live-source smoke verification is required before calling the feature complete.
