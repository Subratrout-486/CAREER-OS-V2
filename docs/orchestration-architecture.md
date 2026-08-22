# Orchestration architecture decision

Use a small typed state machine as the Career OS orchestration contract. This keeps routing and approval behavior deterministic and independently testable while leaving room for a durable graph adapter later.

Research considered LangGraph's checkpointed state and human-in-the-loop model, BoundFlow's explicit Complete/Next/AwaitApproval/AwaitInput outcomes, and lightweight graph implementations that keep policy and routing outside model prompts.

Career OS intentionally does not add a runtime dependency on LangGraph at this stage. The domain contract is smaller than a full graph framework and can be adapted later when durable persistence or remote workers are actually required.