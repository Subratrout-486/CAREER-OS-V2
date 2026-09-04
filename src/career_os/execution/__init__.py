"""Durable, approval-gated application execution subsystem.

This package owns the end-to-end application execution flow:

  DISCOVERED -> ... -> READY_FOR_APPROVAL -> APPROVED -> QUEUED
  -> APPLYING -> SUBMITTED -> SUBMISSION_VERIFIED

plus the failure / security-block / review states. It binds the existing
deterministic pipeline to a browser execution engine behind an explicit human
approval gate. Security challenges are detected and classified as
BLOCKED_SECURITY_CHALLENGE and are never bypassed.
"""

from career_os.execution.challenge import ChallengeDetection, detect_challenge
from career_os.execution.engine import (
    ApplicationExecutionError,
    ApplicationExecutor,
    ExecutionResult,
    Step,
)
from career_os.execution.runner import (
    ApplicationBatchRunner,
    ApplicationPlan,
    BatchOutcome,
)
from career_os.execution.state import (
    ApplicationExecution,
    ApplicationExecutionStateMachine,
    ExecutionStatus,
    ExecutionStore,
)

__all__ = [
    "ApplicationBatchRunner",
    "ApplicationExecution",
    "ApplicationExecutionError",
    "ApplicationExecutionStateMachine",
    "ApplicationExecutor",
    "ApplicationPlan",
    "BatchOutcome",
    "ChallengeDetection",
    "ExecutionResult",
    "ExecutionStatus",
    "ExecutionStore",
    "Step",
    "detect_challenge",
]
