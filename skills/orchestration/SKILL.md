---
name: orchestration
description: Coordinate Career OS specialist agents through durable state, deterministic routing, bounded retries, audit events, and human approval gates.
---

# Orchestration

Use this skill when a workflow spans multiple Career OS departments.

## Rules
- Keep workflow state explicit, persisted, and inspectable.
- Keep deterministic routing outside model prompts.
- Treat specialist agents as domain workers; the orchestrator owns sequencing.
- Persist state after each advancement so a process restart can resume safely.
- Pause before high-impact actions that require human approval and resume the same node after approval.
- Preserve audit events for every node outcome.
- Bound retries and make completed or failed runs idempotent.
- Reject duplicate run IDs instead of silently starting a second workflow.
- Never claim an external side effect occurred without confirmation evidence.
- Keep external providers optional; orchestration must remain testable without credentials.
