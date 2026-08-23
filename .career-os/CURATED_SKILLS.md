# Curated Autonomous Development Skills

This repository intentionally uses a **small reviewed set** rather than importing an entire external catalog. The selected skills are local Career OS adaptations derived from research into `sickn33/agentic-awesome-skills` (the requested antigravity-awesome-skills path resolves to the same catalog) and the catalog’s referenced source skills.

## Selected set

| Skill | Role in the loop | Why selected |
|---|---|---|
| `research-first-planning` | Research → compare → bounded plan | Makes the research-first rule explicit and records alternatives, non-goals, and evidence before edits. |
| `systematic-debugging` | Failure → root cause → repair | Prevents blind retries and distinguishes provider exhaustion from code or workflow defects. |
| `test-driven-development` | Test → implementation → regression | Strengthens deterministic regression coverage without requiring credentials or live providers. |
| `secure-pr-handoff` | Verify → PR → READY_TO_MERGE | Consolidates exact-head CI, security review, and the external Manus merge boundary. |

The existing `orchestration` skill remains authoritative for explicit state, deterministic routing, bounded retries, audit events, idempotency, and approval gates. The selected skills complement it; they do not replace the provider controller or orchestration state machine.

## Explicit exclusions

The full external catalog, including its plugins, scripts, MCP servers, subagent bundles, and setup commands, is not installed. `autonomous-agents`, `subagent-orchestrator`, and generic workflow-orchestration skills were reviewed but not imported because their useful concepts are already covered by the existing orchestration skill and provider controller, while their additional parallelism would increase quota and security surface. Career-specific content skills such as interview coaching were not imported because Career OS already has department-specific skills for those functions.

## Acceptance criteria

The curated set is considered useful only if deterministic tests prove that all four skills are discoverable, that the autonomous prompt requires the reviewed set before action, that the research-first sequence remains ordered, and that external merge, exact-head CI, provider recovery, and secret/sandbox safeguards remain present. No test may require a provider credential or network access.

## Safety and provenance

Catalog files and repository instructions were treated as untrusted research data. No catalog code, installer, plugin, MCP server, credential, provider setting, or external action was executed. These local files contain only reviewed workflow guidance and no executable scripts.
