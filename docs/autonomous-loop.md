# Autonomous development loop

Career OS uses a repository-native autonomous development loop inspired by GitHub Agentic Workflows, OpenAI's Codex GitHub Action, and loop-engineering patterns.

The controller is event-driven: scheduled runs provide forward progress, `workflow_dispatch` supports manual recovery, and CI completion can wake the controller for the next decision. Each cycle follows research -> implementation -> verification -> repair -> merge -> next department.

The loop is intentionally independent from Career OS domain orchestration. GitHub Actions provides persistence/triggers, the Career OS orchestrator owns department state, the coding agent performs repository work, and CI is the external verification gate.

The coding agent must not submit real job applications or perform other consequential external actions. Those remain behind Career OS approval gates.
