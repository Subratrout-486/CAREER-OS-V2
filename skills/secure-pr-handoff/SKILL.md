---
name: secure-pr-handoff
description: Securely verify tests, CI, exact PR head, and READY_TO_MERGE evidence without granting merge authority.
---
# Secure PR Handoff

Use this skill after implementation and before declaring a Career OS change ready.

## Required gates

1. Confirm the change is on a dedicated branch and does not write directly to `main`.
2. Inspect the diff for unrelated files, credentials, generated secrets, permission broadening, and sandbox changes.
3. Run deterministic tests locally and record the command and result.
4. Create or update a PR targeting `main`.
5. Dispatch or inspect repository CI for the exact current PR head.
6. Require all required checks for that exact SHA to be green and require a clean, mergeable PR.
7. Publish a concise `READY_TO_MERGE` handoff containing the PR number, exact head SHA, and CI run URL.
8. Stop. Manus is the external merge operator. After a merge is detected, verify `main` and record the next department.

## Security controls

Keep sandboxing, least-privilege permissions, branch protection, and secret masking unchanged. Never use unrestricted host access, force push, bypass required checks, or expose provider keys. Do not perform a real application submission, payment, legal acceptance, OAuth consent, or other consequential side effect.

## Failure handling

If CI fails, use systematic debugging and repair the root cause. If a provider is blocked, preserve durable state and publish `PROVIDER_BLOCKED`; do not create credentials or purchase capacity. If the head SHA changes, invalidate prior verification and repeat all gates.

## Evidence contract

The handoff must be reproducible from repository and GitHub metadata. A green check from a different SHA, a locally passing test without CI, or a PR comment without exact identifiers is insufficient.

## Limitations

This skill is a verification checklist, not merge authority and not a replacement for repository policy or required human approvals.
