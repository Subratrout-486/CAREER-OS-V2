# Career OS pipeline research

## Sources

1. LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
2. LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
3. Temporal Python durable execution: https://learn.temporal.io/tutorials/python/background-check/durable-execution/

## Findings

LangGraph recommends an explicit graph that mixes deterministic steps with agentic steps and persists thread-scoped checkpoints separately from long-term application state. Temporal emphasizes deterministic workflow definitions, placing external APIs and nondeterministic model calls outside the workflow core, and testing replay compatibility. Both support the same design choice for Career OS: keep the existing dependency-light deterministic orchestration core, make each department a checkpointed step, and place provider calls or external actions behind explicit adapters and gates.

Career OS already has a lightweight `WorkflowOrchestrator`, Pydantic domain models, evidence provenance, deterministic department agents, and an external application-approval boundary. Adding a heavyweight runtime would introduce deployment and dependency cost without solving the current provider-quota issue. The strongest compatible implementation is therefore a repository-native `CareerPipeline` that composes the existing deterministic departments, persists a JSON checkpoint after each step, resumes from the last completed step, and stops before consequential application submission unless explicit approval is supplied.

The pipeline must never infer missing personal facts, submit applications, merge PRs, or bypass CI. Provider use remains optional and outside the deterministic pipeline; provider failures are represented as structured blocked states rather than silently treated as completion.
