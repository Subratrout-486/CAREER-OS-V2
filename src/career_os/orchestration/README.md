# Orchestration

`WorkflowOrchestrator` is the dependency-light execution core for multi-department Career OS workflows.

Use `WorkflowNode` for specialist steps and return an explicit `NodeOutcome`. Persist `WorkflowState` outside the orchestrator when durable resume is required. The state model is intentionally compatible with a later LangGraph/checkpointer adapter.
