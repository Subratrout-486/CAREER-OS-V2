# LinkedIn Authority OS

A career-focused LinkedIn operating layer for Career OS.

## Objective
Turn verified professional knowledge into a repeatable system for positioning, content, engagement, networking, and measurement.

## Architecture

```text
Verified Career Evidence
        |
        v
Positioning + Voice Rules
        |
        +--> Content Engine --> Posts / Carousels
        |
        +--> Engagement Engine --> Target Accounts / Comments
        |
        +--> Relationship Engine --> Warm Conversations
        |
        +--> Analytics Engine --> Weekly Review
                         |
                         +--> experiments + reuse
```

## Execution adapters

The project is designed around explicit adapters:

- `research`: current people, topics, roles, and market context
- `content`: generate and score drafts against the positioning rules
- `linkedin`: publish/comment/profile operations only when a supported authenticated integration is configured
- `analytics`: ingest exported LinkedIn metrics and calculate the Sunday scorecard
- `scheduler`: trigger recurring research/content/review workflows

## Current operating mode

Human-supervised by default. The system can prepare actions automatically but should not impersonate the user or bypass platform safeguards.

## Research notes

Open-source projects demonstrate several viable patterns:

- Playwright + persistent browser profile for local browser control
- MCP servers that expose LinkedIn operations to agents
- OAuth-based LinkedIn integrations for supported API operations
- JSON/CLI interfaces that let an agent orchestrate deterministic actions

The implementation should prefer supported API capabilities and use browser automation only where appropriate and permitted.

## Security

Never commit:

- LinkedIn passwords
- browser profiles
- session cookies
- OAuth client secrets
- access tokens
- private analytics exports containing unnecessary personal data

Use environment variables or a local secret manager instead.

## Planned modules

```text
linkedin-authority-os/
├── README.md
├── config/
│   └── strategy.yaml
├── content/
│   ├── calendar.md
│   ├── drafts/
│   └── published/
├── research/
├── engagement/
├── analytics/
├── automation/
└── schemas/
```
