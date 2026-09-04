# ARACHNE control plane & live web application

ARACHNE is the Career OS product UI. It is **not a disconnected admin mock**:
it is the live control plane built directly on the existing Career OS backend /
API architecture (`arachne_api.py`, `execution/`, `orchestration/e2e.py`,
`providers/`, `dashboard/service.py`). Every number on screen is computed from
real persisted state - there are no hardcoded demo metrics.

## Product identity

A living spider web. The brand mark is a radial web; the Web view renders the
real entity graph as a radial web - candidate at the centre, jobs on the inner
ring, companies and verified outcomes further out - connected by their actual
workflow relationships (company, candidate, verified). Motion is purposeful:
live pulse dots, stage glow, animated pipeline progression, live polling.

## Running

```bash
PYTHONPATH=src uvicorn career_os.http_app:app --port 8000
```

Open `http://localhost:8000/`. The single-page application is served from
`dashboard/index.html` and talks to the control-plane API beneath it.

## Backend (control-plane API)

`src/career_os/arachne_control.py` (`create_arachne_control_router`) is the
single router behind the UI. All reads are real; the only state-changing
actions are the human approval gate and withdrawal.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/overview` | Live aggregate totals, pipeline health, provider health, recent failures |
| `GET /api/jobs` / `GET /api/jobs/{id}` | Every job with its full analytic package |
| `GET /api/processed-jobs` | Processed results from the Arachne result index |
| `GET /api/approval-queue` | Jobs awaiting human approval, ranked by fit |
| `POST /api/jobs/{id}/approve` | Move `READY_FOR_APPROVAL → APPROVED` (human gate) |
| `POST /api/jobs/{id}/withdraw` | Withdraw an application |
| `GET /api/executions[ /{id}]` | Execution tracking with live status + stage index |
| `GET /api/history` | All state transitions (workflow history) |
| `GET /api/activity` | Agent activity stream (last 100 events) |
| `GET /api/providers` | Provider health from the model router |
| `GET /api/candidate` / `GET /api/base-resume` | Candidate source of truth + base resume |
| `GET /api/interview` | Interview questions from JD + evidence (deterministic) |
| `GET /api/learning` | Evidence-gated learning plan from verified gaps |
| `GET /api/graph` | Web graph nodes/edges for the spider-web visualisation |
| `POST /api/discover-demo` | Run discovery against a verified fixture and prepare a full analytic package |

## Frontend views

- **Overview** — live autonomous-loop metrics, pipeline, pipeline health, provider health, failures.
- **Web** — real entity network rendered as a radial spider web.
- **Job Discovery** — every job with its live analytical state; "Run discovery" prepares a real package.
- **Job Detail** — JD intelligence, fit/match ring, evidence ledger, **visual tailored resume**, ATS audit, recruiter review, approval actions, live execution pipeline.
- **Approval Queue** — human approval gate with evidence/score/recommendation before deciding.
- **Execution** — real-time `READY → APPROVED → QUEUED → APPLYING → SUBMITTED → VERIFIED` with explicit `FAILED` / `BLOCKED_SECURITY_CHALLENGE` / `NEEDS_REVIEW` states (polling).
- **Workflow History** — every persisted state transition.
- **Interview Prep** — deterministic questions from JD + candidate evidence.
- **Learning** — evidence-gated skill gaps → objectives/practice.
- **Agent Activity** — the departments that produced each stage.
- **Providers** — provider-neutral health (offline/ollama/HTTP).

## Data flow for a job

`POST /api/discover-demo` (or discovery) → `EndToEndOrchestrator.prepare`
runs the full agent chain and persists `jd`, `evidence`, `fit`, `profile`
(tailored bullets + matched keywords), `ats_audit`, and `recruiter_review`
into the `ApplicationExecution.pipeline` dict. The frontend reads these back
through `/api/jobs/{id}`, so JD analysis, evidence-backed fit reasoning,
tailored resume, ATS audit and recruiter review are all first-class, live
content — not file downloads.

## Safety

- The only frontend-triggered mutations are human approve/withdraw.
- Approval never auto-submits and never bypasses a CAPTCHA/security challenge;
  blocked attempts are recorded as `BLOCKED_SECURITY_CHALLENGE`.
- A submission is only shown as verified when there is real confirmation
  evidence; failures/blocked states are shown explicitly.
