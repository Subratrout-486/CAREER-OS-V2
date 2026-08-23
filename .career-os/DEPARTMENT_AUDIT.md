# Career OS V2 Department Audit

Audited from `main` after merge commit `aaaa22a3eee170e80c020feea457a78321e59b42` and the provider-aware controller runs. Status distinguishes deterministic implementation from real provider-backed execution.

| Department | Status | Implemented? | Tested? | Real provider execution verified? | Dependencies | Blockers | Next action |
|---|---|---:|---:|---:|---|---|---|
| Job Scout | deterministic intake/source adapter layer | Yes | Yes | No | source runners, freshness, verification | provider quota for autonomous execution | continue deterministic source regression tests |
| JD Intelligence | deterministic analysis and evidence extraction | Yes | Yes | No | JD models and analyzers | provider quota for autonomous execution | maintain parsing and evidence tests |
| Evidence Analysis | provenance and conflict analysis | Yes | Yes | No | evidence models | provider quota for autonomous execution | maintain conflict and provenance validation |
| Fit Scoring | evidence-backed fit scoring | Yes | Yes | No | JD requirements, evidence | provider quota for autonomous execution | maintain hard-gap and score regressions |
| Resume Tailoring | evidence-constrained tailoring | Yes | Yes | No | resume model, evidence | provider quota for autonomous execution | maintain no-invented-facts checks |
| Resume Rendering | deterministic document rendering | Yes | Yes in CI | No | Playwright Chromium in CI | local sandbox lacks browser executable | keep CI browser validation green |
| ATS Audit | deterministic resume/JD audit | Yes | Yes | No | ATS models | provider quota for autonomous execution | maintain issue severity and provenance tests |
| Recruiter Review | structured reviewer recommendation | Yes | Yes | No | fit, ATS, evidence | provider quota for autonomous execution | maintain shortlist safety checks |
| Application Management | explicit approval and confirmation-evidence gate | Yes | Yes | No | application models | owner approval for consequential submission | never auto-submit; test approval transitions |
| Interview Coach | deterministic question and answer coaching | Yes | Yes | No | interview models, evidence | provider quota for autonomous execution | maintain evidence-grounded coaching tests |
| Learning | deterministic gap-to-plan generation | Yes | Yes | No | learning models, verified gaps | provider quota for autonomous execution | maintain prioritization and resource tests |
| Orchestration | bounded workflow and checkpointed pipeline | Yes | Yes | No | workflow state, pipeline, provider controller | provider quota for live agent cycle | verify recovery and state persistence in CI |

## Provider comparison

| Provider | Credential available by name | Headless Actions path | Repository editing | Sandboxing | Cost/quota state | Decision |
|---|---|---|---|---|---|---|
| Gemini | `GEMINI_API_KEY` exists; value never read | maintained `run-gemini-cli` action | Yes | Docker sandbox and trusted workspace | free-tier quota exhausted in observed run | retain as first provider; cooldown before retry |
| Codex | `OPENAI_API_KEY` exists; value never read | official `codex-action` | Yes | workspace permission profile with `drop-sudo` | API quota exhausted in observed run | retain as fallback; cooldown before retry |
| Copilot | not established | official GitHub ecosystem path exists | likely, but authorization not established | engine-specific | entitlement/authorization not established | do not configure without authorized credential |
| Claude | not established | external action/integration options exist | possible | engine-specific | provider authorization not established | do not configure without authorized credential |
| Pi | not established | experimental/engine-specific | not established | not established | authorization not established | do not use as production fallback |
| DeepSeek Harness | not established | developer-preview/headless path | Yes | project-specific | credential and stable CI support not established | experimental only; not installed |

## Current blocker

Both already-authorized providers reached real action execution but returned quota failures. The controller records `PROVIDER_BLOCKED`, preserves department and phase state, and now records failure kind, provider, model where available, timestamp, and bounded retry eligibility. The loop must not claim provider-backed completion until a later run completes research, repository inspection, implementation, tests, PR, exact-head CI, READY_TO_MERGE, external merge, and main verification.
