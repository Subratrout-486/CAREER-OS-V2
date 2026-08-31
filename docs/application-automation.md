# Application automation

Career OS may hand off a job to the browser application agent only after the normal career pipeline has approved the application and a job-specific resume artifact exists.

## Components

- `scripts/application_agent.py` — controlled Playwright executor.
- `scrapling` — optional resilient web acquisition/session layer for automation work.
- `candidate/source_of_truth.json` — verified candidate data; the agent never invents answers.
- Job-specific resume artifact — must exist before an application attempt.

## Runtime

The agent supports either:

1. `APPLICATION_BROWSER_PROFILE` — a persistent local Chromium profile. This is the preferred local mode because the user can authenticate normally in the browser.
2. `APPLICATION_BROWSER_CDP_URL` — an already-authenticated Chromium endpoint. This is intended for a controlled remote browser/runner.

No credentials, cookies, session storage, CAPTCHA tokens, or authentication secrets are committed to Git.

## Safety gates

The agent pauses on:

- missing application approval
- missing job-specific resume
- missing application URL
- job-closed indicators
- CAPTCHA/security verification
- unsupported/unknown application fields
- ambiguous submit controls
- missing submission confirmation

A successful browser click is not enough to mark an application as submitted. Submission must have observable confirmation evidence.

## Production setup

A persistent authenticated browser is an external prerequisite. GitHub-hosted runners are ephemeral, so a production deployment should use either a controlled self-hosted runner or a remote browser reachable through `APPLICATION_BROWSER_CDP_URL`.

The browser must be authenticated by the account owner through the normal site login flow. The system does not store or manufacture credentials.

## CAPTCHA/security challenges

Scrapling has browser/stealth and Cloudflare challenge capabilities, but application automation must not treat anti-bot bypass as permission to defeat arbitrary site security controls. When an application presents a human/security verification that cannot be completed through the normal authenticated session, the agent pauses.

## Result states

- `blocked` — precondition failed.
- `paused` — user/security/unknown-field intervention required.
- `submitted_unverified` — a submit action occurred but confirmation was not observed.
- `submitted` — submission confirmation was observed.

Only `submitted` is eligible for a later Notion transition to an applied/submitted state, and that transition should include the recorded evidence URL/result.
