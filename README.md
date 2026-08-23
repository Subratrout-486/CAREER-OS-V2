# CAREER-OS-V2

CAREER-OS-V2 is a fresh rebuild of Career OS, being developed incrementally and deliberately **one department at a time**.

The project includes a portable Agent Skills layer and a deterministic automation core. Skills are small, independently testable capability packages that can be discovered and loaded progressively by the runtime without requiring a model provider or external connector.

## Current scope

The foundation includes:

- a Python package and CI baseline;
- a portable `SkillRegistry` for discovering and validating `SKILL.md` skills;
- ten Career OS capability definitions: Job Scout, JD Intelligence, Evidence Agent, Fit Scorer, Resume Tailor, ATS Auditor, Recruiter Reviewer, Application Manager, Interview Coach, and Learning Agent;
- deterministic public-ATS discovery adapters and a unified provider registry;
- a deterministic, checkpointed end-to-end pipeline composing job intake, JD intelligence, evidence analysis, fit scoring, resume tailoring, ATS audit, recruiter review, and application readiness;
- a provider-free autonomous runner that can discover public ATS jobs and evaluate them without Gemini, Codex, API keys, or other LLM credentials.

The deterministic automation deliberately does **not** auto-submit applications, accept legal/consent terms, spend money, bypass CAPTCHAs, or invent candidate evidence. Those actions remain explicit approval boundaries.

## Provider-free autonomous automation

The scheduled GitHub Actions workflow `.github/workflows/career-os-autonomous.yml` does not invoke Gemini, Codex, or any other AI provider. It installs the repository, runs the deterministic test suite, scans configured public ATS sources, evaluates matching jobs through the local Career OS pipeline, and uploads an auditable JSON report.

Configure public careers URLs in `config/public_ats_sources.json`. Supported public ATS routing currently includes Greenhouse, Lever, Ashby, Workday, Rippling, SmartRecruiters, and Teamtailor. The configuration is intentionally empty by default so no company is contacted until a source is explicitly configured.

```bash
python scripts/career_os_automation.py \
  --sources config/public_ats_sources.json \
  --candidate candidate/source_of_truth.json \
  --output .career-os/automation-run.json
```

This mode is intentionally deterministic. It provides reliable discovery, filtering, evidence-grounded fit scoring, resume prioritization, ATS checks, application-readiness decisions, checkpoints, and reporting. It does not claim LLM-level semantic reasoning; an optional provider can be added later as an enrichment adapter without becoming a dependency of the core automation.

## End-to-end pipeline

`CareerPipeline` composes the deterministic department stages in this order: job intake, JD intelligence, evidence analysis, fit scoring, resume tailoring, ATS audit, recruiter review, and application readiness. It persists an atomic JSON checkpoint after each stage. The pipeline does not call providers, merge pull requests, submit applications, or infer missing personal facts.

```python
from pathlib import Path
from career_os.pipeline import CareerPipeline

pipeline = CareerPipeline(Path(".career-os/pipeline-checkpoint.json"))
result = pipeline.run(run_id="candidate-role-001", raw_job=raw_job, resume=resume, claims=claims)
```

## Research basis

The provider-free design was informed by current open-source patterns rather than copied wholesale. `santifer/career-ops` demonstrates zero-token public ATS scanning, deduplication, liveness verification, and a human-controlled application boundary. `narendranathe/tailor-resume` demonstrates a deterministic weighted ATS gate and an explicit refusal to fabricate missing evidence. GitHub's current Agentic Workflows documentation recommends combining deterministic Actions with optional agentic reasoning rather than replacing deterministic automation with agents. These patterns fit Career OS's existing evidence and checkpoint architecture.

## Development

The project requires Python 3.11 or newer. Install the development dependencies and run the test suite with:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

To install the optional OpenAI Agents SDK in a future development environment, use:

```bash
python -m pip install -e ".[openai-agents]"
```

## Design principles

- Research existing open-source patterns before implementing a new capability.
- Keep deterministic business rules outside model prompts where practical.
- Preserve provenance and distinguish verified evidence from inference.
- Make each department independently testable.
- Treat external integrations and authentication as explicit boundaries rather than hidden dependencies.
- Persist checkpoints at stage boundaries.
- Keep optional nondeterministic provider calls outside the deterministic pipeline core.
