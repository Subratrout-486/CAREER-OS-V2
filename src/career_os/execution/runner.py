"""Durable orchestration runner for approved application executions.

The runner drives the full application lifecycle for a batch of approved jobs:

  APPROVED -> QUEUED -> APPLYING -> SUBMITTED -> SUBMISSION_VERIFIED

and transitions failures / security blocks / review states. A single failing
application never aborts the rest of the batch. State persists after every
externally visible transition so an interrupted run resumes safely.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from career_os.execution.engine import (
    ApplicationExecutionError,
    ApplicationExecutor,
    ApplicationPlan,
    ExecutionResult,
    Step,
)
from career_os.execution.flow import detect_application_flow
from career_os.execution.state import (
    ApplicationExecution,
    ApplicationExecutionStateMachine,
    ExecutionStatus,
    ExecutionStore,
)


@dataclass
class BatchOutcome:
    total: int
    approved: int = 0
    queued: int = 0
    applying: int = 0
    submitted: int = 0
    verified: int = 0
    blocked_security: int = 0
    auth_required: int = 0
    unsupported: int = 0
    failed: int = 0
    needs_review: int = 0
    skipped: int = 0
    results: dict[str, ExecutionResult] = field(default_factory=dict)


class ApplicationBatchRunner:
    """Run an approved batch autonomously, isolating per-job failures."""

    def __init__(
        self,
        store: ExecutionStore,
        machine: ApplicationExecutionStateMachine,
        executor: ApplicationExecutor | None = None,
        *,
        plan_builder: Callable[[ApplicationExecution], ApplicationPlan] | None = None,
    ) -> None:
        self.store = store
        self.machine = machine
        self.executor = executor or ApplicationExecutor()
        self.plan_builder = plan_builder or _default_plan_builder

    def approve_batch(self, executions: list[ApplicationExecution]) -> list[ApplicationExecution]:
        approved: list[ApplicationExecution] = []
        for execution in executions:
            try:
                self.machine.approve(execution)
                self.store.save(execution)
                approved.append(execution)
            except Exception:  # noqa: BLE001, S112 - one unapprovable job must not abort the batch
                continue
        return approved

    def queue_batch(self, executions: list[ApplicationExecution]) -> list[ApplicationExecution]:
        queued: list[ApplicationExecution] = []
        for execution in executions:
            if not self.machine.should_execute(execution):
                continue
            self.machine.queue(execution)
            self.store.save(execution)
            queued.append(execution)
        return queued

    async def execute_batch(self, queued: list[ApplicationExecution]) -> BatchOutcome:
        outcome = BatchOutcome(total=len(queued))
        for execution in queued:
            target = _find_by_id(self.store.list(), execution.execution_id) or execution
            if target.status != ExecutionStatus.QUEUED:
                outcome.skipped += 1
                continue
            outcome.approved += 1
            result = await self._execute_one(target)
            outcome.results[target.execution_id] = result
            if result.security_blocked:
                outcome.blocked_security += 1
            elif result.auth_required:
                outcome.auth_required += 1
            elif result.state == "unsupported":
                outcome.unsupported += 1
            elif result.submitted:
                outcome.submitted += 1
                outcome.verified += 1
            else:
                outcome.failed += 1
        return outcome

    async def _execute_one(self, execution: ApplicationExecution) -> ExecutionResult:
        self.machine.begin_apply(execution)
        self.store.save(execution)
        outcome: ExecutionResult

        try:
            flow = detect_application_flow(execution.application_url or "")
            if not flow.supported:
                self.machine.unsupported(
                    execution,
                    f"Unsupported auto-apply flow: {flow.name} ({flow.detail})",
                )
                self.store.save(execution)
                return ExecutionResult(
                    submitted=False,
                    evidence=(),
                    blockers=(flow.detail,),
                    state="unsupported",
                    reason=f"Unsupported auto-apply flow: {flow.name}",
                    details={"flow_kind": flow.kind.value, "flow_name": flow.name},
                )

            plan = self.plan_builder(execution)
            result = await self.executor.run(
                url=plan.url,
                profile=plan.profile,
                fields=plan.fields,
                steps=plan.steps,
                resume_path=plan.resume_path,
                support_docs=plan.support_docs,
                fixture_pages=plan.fixture_pages,
            )
            outcome = result
        except ApplicationExecutionError as exc:
            outcome = ExecutionResult(
                submitted=False,
                evidence=(),
                blockers=(str(exc),),
                state="error",
                reason=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - boundary must survive unexpected driver errors
            outcome = ExecutionResult(
                submitted=False,
                evidence=(),
                blockers=(str(exc),),
                state="error",
                reason=str(exc),
            )

        if outcome.security_blocked:
            self.machine.block_security_challenge(execution, outcome.reason)
        elif outcome.auth_required:
            self.machine.auth_required(execution, outcome.reason or "Authentication required")
        elif outcome.submitted:
            self.machine.mark_submitted(execution, "; ".join(outcome.evidence))
            self.machine.verify_submission(execution, "; ".join(outcome.evidence))
            execution.execution["result"] = {
                "evidence": list(outcome.evidence),
                "details": outcome.details,
            }
        else:
            self.machine.fail(execution, outcome.reason or "application did not submit")
            execution.execution["result"] = {
                "blockers": list(outcome.blockers),
                "details": outcome.details,
            }

        self.store.save(execution)
        return outcome


def _find_by_id(
    all_executions: list[ApplicationExecution], execution_id: str
) -> ApplicationExecution | None:
    for execution in all_executions:
        if execution.execution_id == execution_id:
            return execution
    return None


def _default_plan_builder(execution: ApplicationExecution) -> ApplicationPlan:
    """A conservative default plan from the execution's prepared pipeline data."""
    pipeline = execution.pipeline or {}
    url = execution.application_url or ""
    profile = pipeline.get("profile", {}) or {}
    fields = pipeline.get("fields", []) or []
    steps = [
        Step(kind="open", target=url),
    ]
    for index, field_spec in enumerate(fields):
        key = str(field_spec.get("key", f"field-{index}"))
        steps.append(
            Step(kind="fill" if field_spec.get("input_type") != "select" else "select", target=key)
        )
    steps.append(Step(kind="click", target="submit"))
    steps.append(Step(kind="wait"))
    steps.append(Step(kind="verify", target=url))
    return ApplicationPlan(
        execution_id=execution.execution_id,
        url=url,
        profile=profile,
        fields=fields,
        steps=steps,
        resume_path=pipeline.get("resume_path"),
        support_docs=pipeline.get("support_docs") or [],
    )
