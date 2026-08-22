---
name: orchestration
description: Coordinate Career OS specialist agents through explicit state, deterministic routing, bounded retries, audit events, and human approval gates.
---

# Orchestration

Use this skill when a workflow spans multiple Career OS departments.

## Rules
- Keep workflow state explicit and inspectable.
- Keep deterministic routing outside model prompts.
- Treat specialist agents as domain workers; the orchestrator owns sequencing.
- Pause before high-impact actions that require human approval.
- Preserve audit events for every node outcome.
- Bound retries and make completed runs idempotent.
- Never claim an external side effect occurred without confirmation evidence.
- Keep external providers optional; orchestration must remain testable without credentials.
