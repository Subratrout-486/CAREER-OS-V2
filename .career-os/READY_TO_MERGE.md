# Autonomous merge handoff

The autonomous development loop must not merge its own PRs.

When a change reaches an exact-head green CI state, the agent must mark the PR `READY_TO_MERGE` with the exact PR number, head SHA, and CI run URL. An external merge operator such as Manus may then verify those facts and merge the PR.

After merge, the CI completion event wakes the next autonomous cycle.
