"""Portal-aware auto-apply adapter for approved Career OS application packages.

The adapter is the clean interface between the prepared, *approved* execution
and the browser application engine. Given an approved ``ApplicationExecution``
it:

1. Classifies the application flow from the employer URL / ATS (Greenhouse,
   Lever, Ashby, generic form, or unknown) - see
   :func:`career_os.execution.flow.detect_application_flow`.
2. Builds a portal-aware application plan.
3. Drives the existing approval-gated engine.
4. Returns a structured :class:`AutoApplyResult` that distinguishes every
   contract state: SUBMITTED, SUBMISSION_VERIFIED, NEEDS_REVIEW, AUTH_REQUIRED,
   BLOCKED_SECURITY_CHALLENGE, UNSUPPORTED and FAILED.

Nothing is ever submitted on an external site without explicit human approval,
and no security challenge is bypassed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from career_os.execution.engine import ApplicationExecutor, ExecutionResult
from career_os.execution.flow import (
    ApplicationFlow,
    FlowKind,
    build_application_plan,
    detect_application_flow,
)
from career_os.execution.state import ApplicationExecution

__all__ = [
    "ApplicationFlow",
    "AutoApplyAdapter",
    "AutoApplyResult",
    "FlowKind",
    "build_application_plan",
    "detect_application_flow",
]


@dataclass
class AutoApplyResult:
    """Structured result of one auto-apply attempt.

    Exactly one outcome flavour is ``True`` reflecting the terminal state:
    submitted / verified / needs_review / auth_required / blocked_security /
    unsupported / failed. This maps 1:1 onto the Career OS execution statuses.
    """

    submitted: bool = False
    verified: bool = False
    needs_review: bool = False
    auth_required: bool = False
    blocked_security: bool = False
    unsupported: bool = False
    failed: bool = False
    flow: ApplicationFlow | None = None
    evidence: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    @property
    def status(self) -> str:
        from career_os.execution.state import ExecutionStatus

        if self.verified:
            return ExecutionStatus.SUBMISSION_VERIFIED
        if self.submitted:
            return ExecutionStatus.SUBMITTED
        if self.auth_required:
            return ExecutionStatus.AUTH_REQUIRED
        if self.blocked_security:
            return ExecutionStatus.BLOCKED_SECURITY_CHALLENGE
        if self.unsupported:
            return ExecutionStatus.UNSUPPORTED
        if self.needs_review:
            return ExecutionStatus.NEEDS_REVIEW
        if self.failed:
            return ExecutionStatus.APPLICATION_FAILED
        return ExecutionStatus.APPLYING

    @staticmethod
    def from_execution_result(result: ExecutionResult, flow: ApplicationFlow) -> AutoApplyResult:
        if result.security_blocked:
            return AutoApplyResult(
                blocked_security=True,
                flow=flow,
                blockers=result.blockers,
                details=result.details,
                reason=result.reason,
            )
        if result.auth_required:
            return AutoApplyResult(
                auth_required=True,
                flow=flow,
                blockers=result.blockers,
                details=result.details,
                reason=result.reason,
            )
        if result.submitted:
            return AutoApplyResult(
                submitted=True,
                verified=True,
                flow=flow,
                evidence=result.evidence,
                details=result.details,
                reason=result.reason,
            )
        return AutoApplyResult(
            needs_review=True,
            flow=flow,
            blockers=result.blockers,
            details=result.details,
            reason=result.reason or "Application did not reach a clear terminal state",
        )

    @staticmethod
    def unsupported_result(flow: ApplicationFlow, reason: str) -> AutoApplyResult:
        return AutoApplyResult(
            unsupported=True,
            flow=flow,
            blockers=(reason,),
            reason=reason,
            details={"flow_kind": flow.kind.value, "flow_name": flow.name},
        )


class AutoApplyAdapter:
    """Drive an approved Career OS package through the application engine.

    This is the dedicated auto-apply boundary: consume an approved package,
    classify its portal/flow, refuse unsupported flows with a clear
    UNSUPPORTED result, and run supported flows through the approval-gated
    engine, returning a structured :class:`AutoApplyResult`.

    The design is a native, embeddable boundary informed by the surveyed
    auto-apply reference projects (AIHawk's portal abstraction and JustHireMe's
    supported-vs-experimental model) - none of those standalone tools are
    imported.
    """

    def __init__(
        self,
        executor: ApplicationExecutor | None = None,
        *,
        flow_detector: Any = None,
        plan_builder: Any = None,
    ) -> None:
        self.executor = executor or ApplicationExecutor()
        self._flow_detector = flow_detector or detect_application_flow
        self._plan_builder = plan_builder or build_application_plan

    async def apply(self, execution: ApplicationExecution) -> AutoApplyResult:
        """Run one approved application; never touches an unsupported flow."""
        flow = self._flow_detector(execution.application_url or "")
        if not flow.supported:
            return AutoApplyResult.unsupported_result(
                flow, f"Unsupported auto-apply flow: {flow.name} ({flow.detail})"
            )

        plan = self._plan_builder(execution)
        result = await self.executor.run(
            url=plan.url,
            profile=plan.profile,
            fields=plan.fields,
            steps=plan.steps,
            resume_path=plan.resume_path,
            support_docs=plan.support_docs,
            fixture_pages=plan.fixture_pages,
        )
        return AutoApplyResult.from_execution_result(result, flow)
