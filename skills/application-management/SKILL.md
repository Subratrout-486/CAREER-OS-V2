---
name: application-management
description: Manage job application state, evidence, follow-ups, deadlines, and submission readiness without silently submitting applications.
---

# Application Manager

Use this skill to track and prepare applications.

## Workflow
1. Maintain a single state machine for each application.
2. Record source, target role, resume version, readiness findings, and timestamps.
3. Track follow-ups and deadlines as explicit events.
4. Require an explicit approval boundary before an external submission.
5. Keep an auditable history of state transitions.

## Rules
- Never claim an application was submitted unless a submission result is confirmed.
- Never overwrite prior application evidence without retaining history.
