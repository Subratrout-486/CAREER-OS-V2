# Follow-Up Department

Career OS treats follow-up as a durable planning step, not an automatic outbound action.

## State model

A follow-up may be scheduled only after a confirmed `SUBMITTED` transition. Interview-stage applications may also carry a follow-up timestamp. Rejected, withdrawn, and closed applications are never eligible.

## Decision flow

```text
confirmed submission / interview event
              |
              v
       durable follow_up_at
              |
              v
        is application active?
          /            \
        no              yes
        |                |
      stop          timestamp due?
                       /      \
                     no        yes
                     |          |
                   wait     create deterministic
                            review action
                                  |
                                  v
                           human decides/send
```

## Safety properties

- Submission must have confirmation evidence before the submitted timestamp exists.
- Re-evaluating a due application returns the same deterministic action rather than appending duplicate application events.
- The planner never sends recruiter messages or performs external communication.
- Status is re-checked before any downstream execution.
- Follow-up scheduling uses timezone-aware timestamps.

## Research basis

Open-source job trackers commonly model follow-up reminders from application dates, and more advanced trackers combine follow-up reminders with application state and ghost-response detection. The implementation here deliberately keeps the external communication step human-controlled. This is consistent with durable human-in-the-loop workflow patterns where approvals/actions must survive retries and state changes.
