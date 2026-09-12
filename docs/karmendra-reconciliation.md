# Karmendra AI Job Hunter → Career OS V2 reconciliation

The Karmendra AI build guide is used as a product-completeness reference for Career OS V2. Career OS does **not** copy the guide's Node.js/Next.js stack or create a second dashboard. ARACHNE remains the single control plane.

## Already present in Career OS V2

| Karmendra capability | Career OS V2 implementation |
|---|---|
| Public ATS discovery | `src/career_os/integrations/ats*`, `src/career_os/discovery/service.py`, optional Scrapling/public APIs |
| Normalization + deduplication | `JobDiscoveryService` + deterministic job intake |
| JD analysis | `JDIntelligence` |
| Evidence-backed fit scoring | `EvidenceAnalyzer` + `FitScorer` |
| Truthful resume tailoring | `ResumeTailor` + candidate Source of Truth |
| ATS audit | `ATSAuditor` |
| Recruiter review | `RecruiterReviewer` |
| Human approval gate | `ApplicationExecutionStateMachine` + ARACHNE approval queue |
| Browser application execution | `ApplicationExecutor` + Playwright driver |
| Dry-run / fixture execution | `DeterministicFixtureDriver` |
| CAPTCHA/security parking | `detect_challenge()` + `BLOCKED_SECURITY_CHALLENGE` |
| Authentication wall handling | `detect_auth_required()` + `AUTH_REQUIRED` |
| Unsupported-flow handling | portal classifier + `UNSUPPORTED` |
| Durable execution state | `ExecutionStore` + explicit state machine |
| Submission confirmation evidence | execution result evidence + `SUBMISSION_VERIFIED` |
| Live dashboard | `dashboard/index.html` served by `http_app.py` |
| Dashboard control plane | `arachne_control.py` |
| Autonomous recurring cycle | `.github/workflows/career-os-autonomous.yml` |

## Gaps this reconciliation closes

### 1. Real browser sessions must persist across an application

The Playwright driver previously launched a fresh browser for every execution step. That loses form state between `open`, `fill`, `upload`, `click`, and `verify` and is incompatible with a real multi-step ATS form.

The driver now keeps one browser/page session for the complete attempt and closes it after verification.

### 2. Remote/CDP browser support

`APPLICATION_BROWSER_CDP_URL` is now supported by the main execution driver, not only the legacy standalone application script. This permits a controlled external Chromium instance to be attached through Playwright. A Fortress instance can therefore be used as an optional browser engine without replacing the Playwright automation layer.

This is a browser-provider integration point, **not** a CAPTCHA/security bypass mechanism. Security challenges remain terminal human-review states.

### 3. Codespace browser reproducibility

`.devcontainer/devcontainer.json` installs the Career OS development dependencies and Playwright Chromium during Codespace creation. This prevents the known `BrowserType.launch: Executable doesn't exist` failure in a fresh Codespace.

## Deliberate differences from the guide

- ARACHNE remains the only dashboard; no second Next.js dashboard is introduced.
- Python/FastAPI remains the existing runtime rather than replacing it with Node.js.
- Candidate facts continue to come from `candidate/source_of_truth.json`; external job descriptions never become candidate experience.
- Applications remain approval-gated.
- CAPTCHAs, security verification, login/account walls, ambiguous legal/identity questions, and unclear submission confirmation are parked for human review.
- No live employer submission is claimed merely because a browser click occurred.

## Definition of done

Career OS is complete against this reference when a real hunt can:

1. discover legitimate public jobs;
2. normalize and deduplicate them;
3. analyze and score them against verified candidate evidence;
4. generate truthful job-specific resume artifacts;
5. place eligible applications in ARACHNE for explicit approval;
6. execute an approved supported application in one persistent browser session;
7. upload the correct resume and fill only verified answers;
8. stop safely on security/auth/unknown-field conditions;
9. verify successful submission before recording it as submitted; and
10. persist the result so a restart cannot duplicate the application.

A successful fixture test is evidence of the software contract. It is not evidence that a real employer accepted an application.
