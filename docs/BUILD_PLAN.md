# Career OS V2 — Step-by-Step Build Plan

## Objective
Build a self-sufficient personal Career OS that owns career-processing workflow and state. External orchestration such as Conductor is intentionally out of the critical path until the core product is proven.

## Operating principles
- Build and prove one department at a time.
- Every agent must have a typed input, typed output, tools, tests, and an audit record.
- Never invent candidate experience, credentials, salary, or job status.
- Unknown evidence stays `UNKNOWN` until verified.
- Duplicate and ghost-job checks happen before a job enters processing.
- Human approval is required before application submission.
- Engineering agents are separated from career-decision agents.
- Conductor is a future adapter, not a dependency of the core runtime.

## Phases

### Phase 0 — Foundation
- Project layout
- Configuration/provider abstraction
- Typed domain schemas
- Agent contract base
- Run/audit model
- Test harness
- Notion adapter boundary
- OpenAI Agents SDK adapter boundary
- No Conductor dependency

### Phase 1 — Job Scout
Input: verified jobs supplied by the daily discovery process.
Output: canonical job records with source URL, company, title, location, status, verification evidence, duplicate key, and ghost-job decision.

Exit criteria:
- unit tests pass
- duplicate detection tested
- ghost-job checks tested
- one real job accepted

### Phase 2 — JD Intelligence
Input: canonical job.
Output: structured requirements, responsibilities, hard blockers, soft requirements, location, compensation evidence, and normalized keywords.

### Phase 3 — Evidence Agent
Input: structured JD + Career Profile.
Output: requirement-to-evidence mapping with `SUPPORTED`, `PARTIAL`, `UNKNOWN`, or `CONFLICT`.

### Phase 4 — Fit Scorer
Input: JD + evidence map.
Output: fit score, rationale, blockers, risks, and APPLY/SKIP recommendation.

### Phase 5 — Resume Tailor
Input: JD + verified evidence + resume source material.
Output: tailored resume draft plus provenance for every material claim.

### Phase 6 — ATS Auditor
Input: JD + tailored resume.
Output: ATS findings, missing keywords, formatting risks, unsupported claims, and readiness result.

### Phase 7 — Recruiter Reviewer
Input: job + JD + evidence + resume + ATS report.
Output: recruiter-style objections, strengths, interview risk areas, and review decision.

### Phase 8 — Application Manager
Input: approved application package.
Output: application checklist, questions requiring user input, execution state, and application record.

### Phase 9 — Interview Coach
Input: JD + submitted application + candidate profile.
Output: prioritized interview questions, answer framework, and gaps to rehearse.

### Phase 10 — Learning Agent
Input: repeated job outcomes, interview feedback, rejection reasons, and skill gaps.
Output: learning priorities and evidence-backed improvement plan.

### Phase 11 — Internal Orchestration
Connect the proven agents with a small Career OS orchestrator. The orchestrator coordinates typed handoffs, persistence, retries, and approval gates; it is not a generic n8n replacement.

### Phase 12 — Engineering Department
Integrate OpenHands SDK first. Add Aider/mini-SWE-agent/Goose only where a measured need exists.

## Future integration
After the core Career OS passes a complete real-job test from intake through application review, add a clean optional Conductor adapter. Conductor must remain removable without breaking Career OS.
