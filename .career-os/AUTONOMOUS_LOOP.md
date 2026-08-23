# Career OS Autonomous Loop

## Objective

Advance Career OS V2 through its departments until the repository reaches a verified, runnable system or a genuine human-required blocker is reached.

## Mandatory cycle

1. Research existing GitHub/web solutions before inventing an implementation.
2. Select the smallest proven pattern that fits Career OS.
3. Implement on a branch.
4. Add or update deterministic tests.
5. Run the repository CI against the exact implementation head.
6. If CI fails, inspect the actual failure, research the failure mode, fix it, and rerun.
7. When the exact head is green, mark the PR `READY_TO_MERGE` for the authorized external merge operator (Manus). The autonomous coding agent never merges its own PR.
8. After the external operator verifies and merges, record the result and advance to the next eligible department.

## Stop conditions

Stop and record `HUMAN_REQUIRED` only for credentials, authentication/consent, missing user facts, legal/financial acceptance, or real-world external actions that explicitly require the owner.

An authorized GitHub merge handoff to Manus is **not** `HUMAN_REQUIRED`. It is an `EXTERNAL_OPERATOR_REQUIRED` / `READY_TO_MERGE` state.

Do not stop merely because a task is difficult. Research alternatives and continue while the blocker is solvable inside the repository or normal GitHub Actions environment.

## Autonomous scope

The loop may research, edit code, create tests, create branches, create/update PRs, dispatch CI, inspect CI, repair failures, and prepare verified PRs for external merge.

Manus is the authorized external merge operator for verified internal Career OS PRs. Manus must verify the exact head SHA, required CI, and mergeability before merging, then verify `main` after the merge.

Real job applications, external account submissions, purchases, contracts, and other consequential external actions remain approval-gated by Career OS policy.

## Bounds

- Maximum autonomous repair iterations per objective: 8.
- Maximum identical failure retries: 3.
- Never bypass a failing verification gate by changing the gate to make it pass.
- Never claim verification without a successful exact-head CI result.
- Never treat an LLM's assertion of completion as verification.

## State

The source of truth is the repository state plus GitHub PR/CI state. The next cycle must inspect current state rather than assuming the previous cycle completed.

## Merge handoff states

- `READY_TO_MERGE`: exact PR head is verified and CI is green; Manus may perform the merge.
- `EXTERNAL_OPERATOR_REQUIRED`: Manus must perform the authorized merge operation.
- `HUMAN_REQUIRED`: the repository owner must personally act.
