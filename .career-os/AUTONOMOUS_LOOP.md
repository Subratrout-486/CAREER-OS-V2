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
7. Merge only after the exact head is green.
8. Record the result and advance to the next eligible department.

## Stop conditions

Stop and record `HUMAN_REQUIRED` only for credentials, authentication/consent, missing user facts, legal/financial acceptance, or real-world external actions that explicitly require the owner.

Do not stop merely because a task is difficult. Research alternatives and continue while the blocker is solvable inside the repository or normal GitHub Actions environment.

## Autonomous scope

The loop may research, edit code, create tests, create branches, create/update PRs, dispatch CI, inspect CI, repair failures, and merge verified internal changes.

Real job applications, external account submissions, purchases, contracts, and other consequential external actions remain approval-gated by Career OS policy.

## Bounds

- Maximum autonomous repair iterations per objective: 8.
- Maximum identical failure retries: 3.
- Never bypass a failing verification gate by changing the gate to make it pass.
- Never claim verification without a successful exact-head CI result.
- Never treat an LLM's assertion of completion as verification.

## State

The source of truth is the repository state plus GitHub PR/CI state. The next cycle must inspect current state rather than assuming the previous cycle completed.
