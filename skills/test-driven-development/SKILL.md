---
name: test-driven-development
description: Define a deterministic regression test before implementing a Career OS feature or repair.
---
# Test Driven Development

Use this skill before writing production code for a feature or bug fix.

## Red, green, refactor

1. **Red:** Write the smallest test that expresses the intended behavior or reproduces the defect. Include boundary conditions and the relevant persisted state or workflow contract.
2. **Verify red:** Run the focused test and confirm it fails for the expected behavioral reason, not because of a typo, import error, or broken fixture.
3. **Green:** Implement the smallest coherent change that makes the test pass. Do not add speculative abstractions or unrelated refactors.
4. **Refactor:** Improve clarity without changing behavior, then rerun focused and full deterministic tests.

## Career OS test priorities

Test provider selection and failure classification without network calls; checkpoint ordering and restart behavior; durable `PROVIDER_BLOCKED` handoffs; workflow prompt ordering; exact-head and CI gate validation; and the rule that the agent never merges. Use fakes or fixtures for providers and never require a live credential for deterministic tests.

Every externally observable workflow contract must have a re-runnable assertion. Manual success is not a substitute for a recorded test.

## Safety rules

Do not rewrite or remove a failing test merely to obtain green CI. Do not make tests depend on a paid provider, a secret, a clock without control, or an external service when a deterministic fixture can express the behavior.

## Limitations

Test-first development does not replace integration testing, exact-head CI, security review, provider recovery, or human approval for consequential actions.
