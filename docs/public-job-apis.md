# Public job API connectors

CareerOS V2 treats external job APIs as **optional intake sources**. A provider outage, malformed response, rate limit, or missing credential must not stop the other sources or the normal processing pipeline.

## Providers

### Adzuna

- Set repository secrets `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
- Set repository variable `CAREER_OS_ADZUNA_QUERY` (or the shared `CAREER_OS_PUBLIC_JOB_QUERY`).
- Optional variables: `CAREER_OS_ADZUNA_COUNTRY` (default `in`), `CAREER_OS_ADZUNA_LOCATION`, `CAREER_OS_ADZUNA_PAGES`, and `CAREER_OS_ADZUNA_RESULTS_PER_PAGE`.
- The adapter uses HTTPS, bounded retries, timeout, and the provider's documented retry-after value when available.
- Salary values are retained with a `salary_is_predicted` flag; CareerOS must not present predicted salary as employer-disclosed salary.

### Arbeitnow

- No API key is required.
- Set `CAREER_OS_ARBEITNOW_QUERY` or the shared query variable.
- Optional variables: `CAREER_OS_ARBEITNOW_LOCATION`, `CAREER_OS_ARBEITNOW_REMOTE_ONLY`, and `CAREER_OS_ARBEITNOW_PAGES`.
- Results are locally filtered and normalized before entering the common intake pipeline.

### Open Skills

Open Skills is **enrichment only**, not a job source. It can normalize a job title and retrieve related skills.

- Disabled by default.
- Enable with `CAREER_OS_OPEN_SKILLS_ENABLED=true`.
- The historical public endpoint is HTTP, so CareerOS refuses it by default. Prefer an HTTPS-compatible deployment/mirror by setting `CAREER_OS_OPEN_SKILLS_BASE_URL`.
- `CAREER_OS_OPEN_SKILLS_ALLOW_HTTP=true` is an explicit insecure opt-in and should not be used in production.
- If enrichment fails, the job continues through processing with an audit risk signal.

## Failure isolation

The autonomous worker:

1. Fetches each configured provider independently.
2. Normalizes all successful records into `JobRecord`.
3. Deduplicates by canonical URL/content before processing.
4. Enriches titles only when Open Skills is enabled.
5. Processes each job independently using the existing durable CareerOS pipeline.
6. Writes `.career-os/public-job-api-report.json` even when a provider fails.
7. Uses `continue-on-error` at the workflow boundary so a provider outage cannot block Notion intake or the rest of the autonomous cycle.

The adapters deliberately do not scrape a provider's redirected job page to manufacture missing descriptions. If a provider returns incomplete data, the existing pipeline can block that job rather than inventing content.

## Local test

```bash
python -m pytest -q tests/test_public_job_apis.py tests/test_job_intake.py tests/test_source_runner.py
```
