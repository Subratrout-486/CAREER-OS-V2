---
name: systematic-debugging
description: Investigate failures to root cause before making the smallest verified repair in Career OS.
---
# Systematic Debugging

Use this skill for any test failure, CI failure, provider error, unexpected state, or workflow anomaly.

## Four phases

1. **Observe:** Capture the exact command, commit SHA, workflow run, failing check, error text, inputs, and persisted state. Do not paraphrase away useful evidence.
2. **Localize:** Identify the first failing boundary and compare it with the last known-good run or commit. Separate provider failure, orchestration failure, repository failure, test failure, and merge-gate failure.
3. **Hypothesize and reproduce:** State one falsifiable root-cause hypothesis. Reproduce it with a deterministic test or the smallest safe diagnostic. Do not retry blindly.
4. **Repair and verify:** Apply the smallest fix, run the regression test first, then the relevant test suite and exact-head CI. Record the result and remaining risk.

## Safety rules

Never weaken sandboxing, permissions, branch protection, tests, or secret handling to make a failure disappear. Never treat a quota, rate-limit, outage, or unavailable-model error as a code defect. Route provider failures through the provider controller and preserve department state. Never print credentials or copy sensitive provider output into logs, issues, or PRs.

## Career OS verification

A provider-blocked result is a successful durable handoff, not an infrastructure failure. A PR is not merge-ready until its current head exactly matches the recorded SHA, required CI is green for that SHA, it targets `main`, and the agent has not merged it. Record the evidence in the development log.

## Limitations

This skill guides investigation; it does not authorize external side effects, credential changes, bypasses, or merges.
