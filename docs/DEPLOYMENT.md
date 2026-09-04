# Deployment & Production Readiness

This document is the authoritative guide for launching **ARACHNE** (the Career OS
control plane) into production. It covers the backend startup, frontend serving,
environment variables, provider credentials, persistent storage, browser
(Playwright) requirements, health checks, logging, and failure recovery.

ARACHNE is the single user-facing control plane and dashboard for the whole
Career OS lifecycle (discovery → analysis → approval → execution → verification →
history → interview → learning). There is no second dashboard.

---

## 1. Architecture overview

A single FastAPI process (`career_os.http_app:app`) serves both the ARACHNE SPA
and the control-plane API:

| Mount | Router | Purpose |
| --- | --- | --- |
| `/` | static | Serves `dashboard/index.html` (ARACHNE SPA) |
| `/api` | `create_arachne_control_router` | Live control plane (jobs, approval, execution, graph, providers, interview, learning, discovery) |
| `/api/v1` | `create_arachne_router` | Read API for processed results + `/api/v1/health` |
| `/api/v1/state` | `create_state_router` | Execution/snapshot state API |

The AI stage agents (JD intelligence, evidence analysis, fit scoring, resume
tailoring, ATS audit, recruiter review, interview, learning) are **deterministic
and offline** — they never fabricate results and need no credentials. The
provider/router layer is used for optional model enrichment and health reporting
(see §4).

---

## 2. Backend startup

```bash
# from the repository root
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # or .[automation] for browser+scraper extras

# run the ARACHNE control plane
PYTHONPATH=src uvicorn career_os.http_app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/` in a browser.

> The bundled `career_os.http_app:app` is the single entry point. Do not use
> `career_os.arachne_server` (an older minimal ASGI app) for production ARACHNE;
> it does not mount the control-plane router. `career_os.conductor_api` is a
> separate orchestration boundary mounted elsewhere and is not required to run
> the ARACHNE UI.

---

## 2b. Production deployment (making ARACHNE public)

The repository ships a containerised, single-process deploy ready for any host
that runs containers (Render, Railway, Fly.io, a VPS with Docker, etc.). No
second frontend is added; `career_os.http_app:app` serves the ARACHNE SPA at
`/` and the `/api` control plane.

### Container (recommended)

```bash
docker build -t career-os-v2 .
docker run -d --name career-os-v2 \
  -p 8000:8000 \
  -v career_os_data:/data \
  career-os-v2
# open http://127.0.0.1:8000/
```

The image runs `uvicorn career_os.http_app:app` on `0.0.0.0:8000`, runs as a
non-root user, and mounts persistent state under `/data` (execution store,
ARACHNE index). A `HEALTHCHECK` probes `/healthz` every 30s.

### Render blueprint (one-click)

`render.yaml` is a Render Blueprint: a web service (Docker) that mounts a
1 GB persistent disk at `/data` and health-checks `/healthz`. To launch:

1. Push this repo to GitHub.
2. On render.com, click **New + → Blueprint** (or **New + → Web Service** and
   point it at the repo, runtime *Docker*).
3. Render builds the `Dockerfile`. The service becomes public at
   `https://career-os-v2.onrender.com/`.
4. Optionally set `CAREER_OS_ENABLE_BROWSER` only if the image includes
   Playwright/Chromium and you intend live application execution (see §6).

Equivalent one-command deploys on other hosts:
- **Railway:** New Project → Deploy from GitHub → default start command
  already resolves from `Procfile` / `CMD`.
- **Fly.io:** `fly launch` then `fly deploy`.

### Health checks

- `GET /healthz` — token-free liveness/readiness. Returns `{"status":"ok",...}`
  only when the persistent state roots exist and are writable, otherwise a
  `degraded` report listing the failing mounts. This is the probe host
  providers and the Docker `HEALTHCHECK` use.
- `GET /api/v1/health` — token-gated service health (requires
  `CAREER_OS_CONDUCTOR_TOKEN` header when that env is set).
- `GET /api/providers` — provider/agent availability matrix (tokenless).

### What a deployer must provide

- A hosting account (e.g. Render/Railway/Fly) and a way to authenticate from
  this environment (or push to a private/public GitHub the host builds from).
- A public/private repo the host can build from — this repo is already
  pushed to `https://github.com/Subratrout-486/CAREER-OS-V2`.
- Optional secrets only if you enable live browsing (`CAREER_OS_ENABLE_BROWSER`
  + Playwright image) or optional provider enrichment (Ollama/JobPilot/Gmail/
  Notion). The app is fully operational tokenless and offline.

---

## 3. Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `CAREER_OS_EXECUTION_ROOT` | `.career_os/executions` | Execution store root (durable approval + execution state) |
| `CAREER_OS_ARACHNE_ROOT` | `.career_os/arachne` | Processed-job index (ARACHNE read/API + control plane) |
| `CAREER_OS_CONDUCTOR_CHECKPOINT_PATH` | `.career_os/conductor_runs` | Conductor pipeline checkpoints |
| `CAREER_OS_CONDUCTOR_IDEMPOTENCY_PATH` | `.career_os/conductor_idempotency.json` | Conductor idempotency ledger |
| `CAREER_OS_OLLAMA_URL` | `http://localhost:11434` | Local Ollama model endpoint (optional enrichment) |
| `CAREER_OS_ENABLE_BROWSER` | (unset ⇒ off) | `1`/`true` to enable live browser execution (Playwright). Off ⇒ safe deterministic fixture driver. |
| `CAREER_OS_CONDUCTOR_TOKEN` | (unset) | Bearer token required by the `/api/v1` read API + state API when set (HMAC-compared; header `X-Career-OS-Token`) |
| `CAREER_OS_ENV` | (unset) | `production`/`sandbox` operational label |
| `JOBPILOT_API`, `JOBPILOT_API_TOKEN`, `JOBPILOT_TERMINAL_URL`, `JOBPILOT_PROVIDER`, `JOBPILOT_TIMEOUT_SECONDS`, `JOBPILOT_POLL_SECONDS` | (unset) | Optional delegated browser-execution via the user's JobPilot terminal (mutually exclusive with native Playwright: see §6) |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Self-healing CI repair model (CI only) |

---

## 4. Provider / AI routing

`src/career_os/providers/routing.py` centralises model routing with a
**never-fabricate** policy. Health is exposed at `GET /api/providers`.

Honest provider status matrix (as of this commit, verified in this environment):

| Provider | Adapter | Implemented | Configured (creds) | Executed successfully | Blocked by |
| --- | --- | --- | --- | --- | --- |
| **offline** | `OfflineAdapter` | ✅ | ✅ (no creds) | ✅ (returns deterministic, empty enrichment) | — |
| **ollama** | `OllamaAdapter` | ✅ | ⚠️ only if `CAREER_OS_OLLAMA_URL` reachable | ❌ not run (no local Ollama/GPU in this env) | environment (no Ollama service) |
| **http** (base) | `HTTPProviderAdapter` | ✅ (base) | ❌ requires an API-key env variable | ❌ | no concrete credentialed subclass wired / no credential |
| **gmail** (intake script) | `gmail_job_intake.py` | ✅ | ❌ requires OAuth refresh token | ❌ | credentials not provided |
| **notion** (worker scripts) | scripts | ✅ | ❌ requires Notion token | ❌ | credentials not provided |
| **jobpilot** | `JobPilotExecutor` | ✅ | ❌ requires API/terminal creds | ❌ | credentials + a remote terminal |

Resilience guarantees (already implemented and tested):
- `ModelRouter.available(task)` returns the first available adapter for a task
  and falls back to `OfflineAdapter` — never raises and never fabricates.
- `OfflineAdapter.complete()` returns `""` (no invented content).
- `HTTPProviderAdapter.complete()` raises unless the API key is set.
- `OllamaAdapter.complete()` raises a typed `ProviderFailure(kind="temporary")`
  on network error so callers can retry/fallback.
- Failures are recorded via `ModelRouter.record_failure(provider, message)`.

The deterministic stage agents do **not** depend on these providers, so the
system is fully operational with zero credentials.

---

## 5. Persistent storage

All lifecycle state is persisted to disk and survives process restarts via
atomic writes (temp file + rename). Default paths (override via env):

| State | Path | Survives restart |
| --- | --- | --- |
| Execution store (approval, execution, verification, events) | `.career_os/executions/<id>.json` | ✅ |
| Processed-job index (ARACHNE) | `.career_os/arachne/index.json` | ✅ |
| Pipeline checkpoints | `.career_os/automatic_runs/<run_id>.json` | ✅ |
| Conductor checkpoints / idempotency | `.career_os/conductor_runs`, `conductor_idempotency.json` | ✅ |
| Candidate source of truth | `candidate/source_of_truth.json` | ✅ (committed) |
| Tailored PDF resumes | `.career-os/resume/*.pdf` (scripts) | ✅ |

In production, mount a persistent volume so `.career_os/` and `.career-os/`
survive container recreation. The bundled Dockerfile and `render.yaml`
blueprint mount a volume at `/data` and set `CAREER_OS_EXECUTION_ROOT` and
`CAREER_OS_ARACHNE_ROOT` under it; `/healthz` verifies those roots are mounted
and writable. `ssd` or persistent disks recommended; these are small JSON files.

---

## 6. Browser (Playwright) requirements — live application execution

Application execution against a real employer site requires Chromium + Playwright.

**Install (production host):**

```bash
pip install -e ".[automation]"        # playwright + scrapling
python -m playwright install chromium
python -m playwright install-deps     # system deps (optional on many hosts)
```

**Enable live browsing (explicit opt-in):**

```bash
export CAREER_OS_ENABLE_BROWSER=1
```

**How the safety boundary works:**
- With `CAREER_OS_ENABLE_BROWSER` **unset, live browsing is disabled** and the
  runtime uses the deterministic fixture driver — no real employer is contacted,
  and every run carries an explicit `notice` that no live browsing occurred.
- With it set, `build_driver()` returns `PlaywrightExecutionDriver`, which fills
  fields/selects/uploads and returns page signals to the engine. The engine is
  the single judge of challenge detection and submission verification.
- **CAPTCHA / bot challenge**: `execution/challenge.py` detects CAPTCHA /
  reCAPTCHA / hCaptcha / Cloudflare Turnstile / PerimeterX etc. and the engine
  classifies the run as `BLOCKED_SECURITY_CHALLENGE`. There is deliberately **no
  bypass** logic; the application is preserved for human review and never
  reported as successful.
- **Authentication wall**: `execution/auth.py` detects a page that requires the
  user to sign in (login form, "sign/log in" text, login URL, HTTP 401/403).
  The engine classifies the run as `auth_required` and the runner surfaces it as
  `NEEDS_REVIEW` with an "Authentication required" reason. This is **distinct**
  from a CAPTCHA block and from a generic failure — it is never recorded as a
  successful submission, and the engine performs no login or credential use.
- **Verification**: a submission is only recorded `SUBMITTED` → `SUBMISSION_VERIFIED`
  when real confirmation evidence is present. `SUBMITTED` without evidence raises
  `APPLICATION_FAILED`/`missing_evidence`.

**Experimental/optional:** `scripts/application_agent.py` (browser/CDP based) and
`JobPilotExecutor` (delegated to a remote terminal) are alternative execution
paths; the native engine + Playwright driver is the primary path.

---

## 7. Health, startup checks & failure recovery

- **Health endpoint:** `GET /healthz` (token-free liveness/readiness; verifies
  the persistent state roots are mounted and writable). Returns
  `{"status":"ok","service":"career-os-v2","ready":true}`.
- **Service health:** `GET /api/v1/health` (requires `CAREER_OS_CONDUCTOR_TOKEN`
  if set). Returns `{"status":"ok","service":"career-os-v2","submission_enabled":false}`.
- **Provider health:** `GET /api/providers` reports each adapter's availability.
- **Recovery:** every externally visible transition is written atomically
  (`tempfile` + `os.replace`), so a crash mid-write cannot corrupt state. On
  restart the engine reloads persisted executions and resumes safely (verified by
  `tests/test_execution_durability_and_api.py` — restart/resume + idempotency +
  isolated-failure tests).
- **Idempotency:** a batch is never double-submitted; re-running an already
  VERIFIED execution is a no-op.
- **Failure isolation:** one failing job/application never aborts the batch.

---

## 8. Logging

The app uses standard Python logging via the FastAPI/uvicorn logger. Add a
structured logger in production (e.g. `logging` handlers to stdout + a
structured sink). Persisted per-run JSON (`execution.events`, `.career-os/*.json`
reports) is the durable audit trail; `GET /api/history` and `GET /api/activity`
expose it in the UI.

---

## 9. Testing & verification (run before deploy)

```bash
source .venv/bin/activate
PYTHONPATH=src python -m pytest -q              # full suite
ruff check src/ tests/                          # lint
ruff format --check src/ tests/                 # format
# packaged-app smoke (no live network):
PYTHONPATH=src python scripts/arachne_live_smoke.py
```

Known environment-only failures (not code failures): PDF rendering tests require
the Playwright/Chromium executable which cannot be installed/verified in a
sandboxed CI without the `[automation]` extra + `playwright install chromium`.

---

## 10. Known limitations (honest)

1. **No model is executed end-to-end here** — the deterministic agents are fully
   operational offline, but real LLM inference (Ollama) and credentialed
   providers were not run in this environment (no Ollama/GPU/credentials).
2. **Live browser submission is implemented but not executed** — Chromium is not
   installed here. With `CAREER_OS_ENABLE_BROWSER=1` + `playwright install
   chromium`, live runs become active; a real employer contact was deliberately
   not attempted during automated testing.
3. **Eligibility** — an application is `BLOCKED_SECURITY_CHALLENGE` on CAPTCHA/MFA;
   these are preserved for human review, never auto-solved or falsely reported.
4. **Gmail/Notion/JobPilot** worker scripts are implemented but require the user's
   credentials/tokens to execute against those services.
5. **Deployment to a paid/external host was not done** — no credentials were
   provided or guessed. The above config is everything needed once a host and
   credentials are chosen.
