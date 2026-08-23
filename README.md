# CAREER-OS-V2

CAREER-OS-V2 is a fresh rebuild of Career OS, being developed incrementally and deliberately **one department at a time**.

The project now includes a portable Agent Skills layer. Skills are small, independently testable capability packages that can be discovered and loaded progressively by the runtime without requiring a model provider or external connector.

## Current scope

The foundation includes:

- a Python package and CI baseline;
- a portable `SkillRegistry` for discovering and validating `SKILL.md` skills;
- ten Career OS capability definitions: Job Scout, JD Intelligence, Evidence Agent, Fit Scorer, Resume Tailor, ATS Auditor, Recruiter Reviewer, Application Manager, Interview Coach, and Learning Agent;
- Job Scout as the first detailed skill contract, ready to sit above deterministic ATS/source adapters;
- a deterministic, checkpointed end-to-end pipeline composing job intake, JD intelligence, evidence analysis, fit scoring, resume tailoring, ATS audit, recruiter review, and application readiness.

The skill layer does **not** by itself provide autonomous browser automation, application submission, provider fallback, Conductor/MCP integration, or external credentials. Those capabilities will be added only when a later stage requires them.

## Skill format

Each skill lives in its own directory:

```text
skills/<skill-name>/
└── SKILL.md
```

`SKILL.md` uses the portable Agent Skills format with YAML frontmatter containing `name` and `description`, followed by concise operational instructions. Larger references, scripts, or assets can be added inside the same skill directory later.

The runtime discovers metadata without loading unrelated skills and loads the full instruction body only for the requested skill. This keeps the architecture composable and avoids putting every department's rules into one giant prompt.

## End-to-end pipeline

`CareerPipeline` composes the deterministic department stages in this order: job intake, JD intelligence, evidence analysis, fit scoring, resume tailoring, ATS audit, recruiter review, and application readiness. It persists an atomic JSON checkpoint after each stage and resumes only within the same run identifier. The pipeline does not call providers, merge pull requests, submit applications, or infer missing personal facts. Application submission remains behind the explicit `ApplicationManager` approval and confirmation-evidence boundary.

```python
from pathlib import Path
from career_os.pipeline import CareerPipeline

pipeline = CareerPipeline(Path(".career-os/pipeline-checkpoint.json"))
result = pipeline.run(run_id="candidate-role-001", raw_job=raw_job, resume=resume, claims=claims)
```

Provider execution remains owned by the GitHub Actions controller. Provider quota or outage failures are recorded as provider-blocked state and never treated as successful Career OS completion.

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
- Persist checkpoints at stage boundaries and keep nondeterministic provider calls outside the deterministic pipeline core.
