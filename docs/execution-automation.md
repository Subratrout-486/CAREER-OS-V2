# Execution & autonomous application automation

The execution subsystem turns an approved, evidence-backed application plan into
a durable, verifiable submission — without ever bypassing a security challenge
and without inventing candidate facts.

## Design contract

- **Human approval is the boundary.** No application is submitted unless it has
  moved through `READY_FOR_APPROVAL -> APPROVED`. Unapproved jobs are never
  submitted; submissions are only recorded with real verification evidence.
- **Durable state machine** (`execution/state.py`). Every externally visible
  transition is persisted atomically to the `ExecutionStore`. An interrupted run
  resumes safely on restart.
- **Driver-agnostic engine** (`execution/engine.py`). `ApplicationExecutor` runs
  steps (open, fill, select, upload, click, wait, verify) against an
  `ExecutionDriver`. The bundled `DeterministicFixtureDriver` replays synthetic
  HTML fixtures; a real `PlaywrightApplicationDriver` is available for live use.
- **Security challenges stop the run** (`execution/challenge.py`). Detection only
  — classification to `BLOCKED_SECURITY_CHALLENGE`. The system never attempts to
  defeat, evade, or bypass CAPTCHA / bot detection.
- **Evidence before success.** A submission is only marked `SUBMISSION_VERIFIED`
  when the result page confirms it and confirmation evidence is extractable.

## Components

| Module | Responsibility |
| --- | --- |
| `execution/state.py` | `ExecutionStatus` lifecycle, `ExecutionStore` (atomic JSON), state machine with approval gate |
| `execution/engine.py` | `ApplicationExecutor`, `Step`, `ExecutionResult`, `DeterministicFixtureDriver` |
| `execution/runner.py` | `ApplicationBatchRunner`, `ApplicationPlan`, batch isolation & outcome |
| `execution/challenge.py` | Security-challenge detection & classification (no bypass) |
| `execution/browser_driver.py` | Live Playwright driver (fit/scoring hooks set up by caller) |
| `providers/routing.py` | `ModelRouter`, `OfflineAdapter`, `OllamaAdapter`, `HTTPProviderAdapter` (no live keys) |
| `discovery/service.py` | `JobDiscoveryService`: normalize, dedup, freshness/reliability ranking |
| `discovery/scraper.py` | `JobPageScraper` with Scrapling/stdlib/fixture fallback |
| `orchestration/e2e.py` | `EndToEndOrchestrator`: prepare + `run_approved` |
| `state_api.py` | Live FastAPI router for dashboard + execution state |

## Execution flow

```
DISCOVERED -> READY_FOR_APPROVAL -> APPROVED -> QUEUED -> APPLYING
           -> SUBMITTED -> SUBMISSION_VERIFIED    |-> APPLICATION_FAILED
                                                  |-> BLOCKED_SECURITY_CHALLENGE
                                                  |-> NEEDS_REVIEW
```

## Running

```bash
PYTHONPATH=src python -m pytest tests/test_execution_subsystem.py \
    tests/test_discovery_and_e2e.py tests/test_execution_durability_and_api.py -q
```

The HTTP app serves live dashboard + execution state:

```bash
PYTHONPATH=src uvicorn career_os.http_app:app --port 8000
```

- `GET /api/v1/state/dashboard` — aggregate metrics
- `GET /api/v1/state/executions` — execution list
- `GET /api/v1/state/executions/{id}` — one execution with full event log
