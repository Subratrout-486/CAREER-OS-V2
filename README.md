# CAREER-OS-V2

CAREER-OS-V2 is a fresh rebuild of Career OS, being developed incrementally and deliberately **one department at a time**.

This repository currently contains the project foundation only. It establishes the Python package layout, test configuration, and continuous integration baseline so that future work can proceed in small, reviewable steps.

## Current scope

The V2 foundation does not implement Career OS agents, departments, an orchestrator, provider fallback, application automation, or domain workflows. It also contains no external connectors, integrations, credentials, API keys, browser automation, or copied code from the previous Career-OS repository.

The OpenAI Agents SDK is available only as an optional dependency for future, explicitly scoped work. No external AI provider is mandatory for installing or importing the foundation package.

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

Future departments and capabilities will be introduced incrementally, with their own tests and documentation, while keeping the foundation independently importable and testable.
