# Career OS V2 Development Log

## Current status

The repository has a verified deterministic department layer and a provider-neutral GitHub Actions controller. The current implementation adds a checkpointed end-to-end pipeline, but full system completion still requires a successful provider-backed autonomous cycle and any remaining department-specific integrations to be verified in GitHub Actions.

## Completed and merged

| Area | Evidence |
|---|---|
| Foundation and skills registry | Main history and passing CI |
| Job Scout and ATS/source intake | Existing deterministic agents and tests |
| Recruiter Reviewer | PR #2 merged after exact-head CI success; merge commit `b9361e74fc7934f5aa20d6fac77b043b8922fa23` |
| JD Intelligence | PR #9 merged after exact-head CI success; merge commit `c3dfe1ef977416ecb924627266d3c84afe4b8f64` |
| Autonomous workflow safety repair | PRs #13 and #15 merged; maintained Gemini Action, workspace trust, and sandbox controls |
| Provider-neutral controller | PR #16 merged; exact-head CI passed; main merge commit `39b862e959706ed7c4cdcca69740adfe6bc73552` |

## Current department

The deterministic end-to-end pipeline is the current implementation focus. Its stages are job intake, JD intelligence, evidence analysis, fit scoring, resume tailoring, ATS audit, recruiter review, and application readiness. It checkpoints after every stage and stops conservatively on missing descriptions or evidence conflicts.

## Provider failures and fixes

The Gemini provider reached actual CLI/API execution but exhausted its free-tier quota. The authorized Codex fallback was then attempted and also returned `Quota exceeded. Check your plan and billing details.` No credentials were created, purchased, exposed, or replaced. The controller recorded `PROVIDER_BLOCKED` rather than claiming a successful autonomous cycle.

## Verification

Focused pipeline tests pass locally. The full local suite has one environment-only failure when Playwright Chromium is not installed; repository CI installs Chromium and has previously passed the full suite. A post-merge provider-aware cycle must still be rerun when an authorized provider has available quota.

## Remaining work

The next cycle should run the checkpointed pipeline and continue any unfinished department. Each feature must follow research, implementation, deterministic tests, exact-head CI, external merge, main verification, and post-merge execution. Consequential application submission remains approval-gated.

## Autonomous audit and provider recovery enhancement

The declared departments are implemented as deterministic modules and have dedicated tests: Job Scout, JD Intelligence, Evidence Analysis, Fit Scoring, Resume Tailoring, Resume Rendering, ATS Audit, Recruiter Review, Application Management, Interview Coach, Learning, and Orchestration. Real provider-backed execution remains unverified for department work because Gemini and Codex are quota-blocked; the controller correctly records `PROVIDER_BLOCKED`.

The controller now classifies configuration failures separately from authorization failures, persists provider, model, timestamp, failure kind, and retry eligibility, applies bounded cooldowns for quota/rate-limit/temporary/outage/model-unavailable failures, preserves department and phase state, and avoids repeated requests while a provider is in cooldown. Unknown and authorization/configuration failures are not automatically retried. The workflow remains provider-neutral, research-first, sandboxed, least-privilege, and merge-boundary safe.

Focused recovery tests pass. The full local suite is otherwise green except for the known environment-only Playwright Chromium executable absence; GitHub CI installs Chromium. Remaining work is to verify the recovery behavior in GitHub Actions and run a genuine provider-backed department cycle when an authorized provider has available quota.


## Curated autonomous-development skills

Research was performed against `sickn33/agentic-awesome-skills` (the requested antigravity-awesome-skills path resolves to that catalog) and selected source skill documents. The full catalog was not installed or executed. Existing Career OS orchestration already covers explicit state, deterministic routing, bounded retries, audit events, idempotency, and approval gates. The smallest non-duplicative high-value set was selected: `research-first-planning`, `systematic-debugging`, `test-driven-development`, and `secure-pr-handoff`.

These four skills were implemented as reviewed local instruction files with no executable payloads. The autonomous prompt now requires the curated set and explicitly forbids external catalog installation. The manifest records provenance, exclusions, safety rules, and acceptance criteria. Providers, credentials, sandbox settings, and the provider controller were not changed.

Focused curated-skill and workflow tests pass: 13 passed. The full deterministic suite excluding the environment-dependent PDF browser test passes: 190 passed. The complete local suite still has the known Playwright Chromium executable absence; this is an environment limitation, not a curated-skill failure. The branch is ready for CI validation; no merge is authorized until exact-head CI is green.


## Application Management safety hardening

With provider-dependent work blocked, Application Management was selected as the highest-value unblocked department because it guards consequential external submission. Research covered GitHub environment approval gates, AWS Step Functions human approval, and Temporal idempotency guidance. The existing state machine already required explicit approval and confirmation evidence; the concrete gap was that whitespace-only evidence was accepted as a submission confirmation.

A test-first regression was added and confirmed red before implementation. The transition guard now rejects missing or whitespace-only submission evidence without recording a state transition. Focused Application Management tests pass, and the full deterministic suite has 211 passing tests with only the known local Playwright Chromium executable limitation in the PDF rendering test. The change is ready for dedicated-branch PR and exact-head CI verification; no provider, credential, sandbox, or merge-boundary changes were made.
