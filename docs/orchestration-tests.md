# Orchestration verification cases

The orchestration suite covers:

- linear completion;
- audit event creation;
- approval pause/resume;
- rejected approval blocking execution;
- idempotent replay after completion;
- bounded retries.

Provider credentials and model calls are intentionally absent from these tests so the workflow core remains deterministic and fast.
