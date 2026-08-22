# Career OS orchestration

Career OS uses a dependency-light workflow state machine around specialist agents.

## Pattern

1. Typed workflow state is the source of truth.
2. Specialist nodes perform domain work; the orchestrator owns routing.
3. Outcomes are explicit: next, complete, approval, input, retry, or fail.
4. Approval pauses the workflow instead of allowing a high-impact node to proceed.
5. Audit events record each node outcome.
6. Completed runs are idempotent on replay.
7. Retries are bounded per node.

The implementation intentionally does not require LangGraph. A later adapter can map these primitives to a durable graph runtime without changing specialist-agent contracts.
