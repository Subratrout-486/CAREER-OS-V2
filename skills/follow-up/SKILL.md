---
name: follow-up
description: Plan and track application follow-ups using application state, confirmed submission timestamps, and explicit human review.
---

# Follow-Up Manager

Use this skill to identify when an application needs a follow-up without silently contacting recruiters.

## Workflow
1. Read the canonical application record and current status.
2. Only schedule a follow-up after a confirmed submission or an explicitly recorded interview-stage event.
3. Use the stored follow-up timestamp as the durable source of truth.
4. Generate a follow-up action when the timestamp is due and the application is still active.
5. Keep the action pending human review; never send or submit an external message automatically.
6. Reschedule only after an explicit state update or user-directed follow-up interval.

## Rules
- Never create a follow-up for an unsubmitted, rejected, withdrawn, or closed application.
- Never infer that an application was submitted from an approval state alone.
- Never auto-send recruiter messages.
- Follow-up evaluation must be idempotent: evaluating the same application repeatedly must not create duplicate actions.
- Preserve the application event history and existing evidence.
- If the application status changes before execution, re-check eligibility before presenting the action.
