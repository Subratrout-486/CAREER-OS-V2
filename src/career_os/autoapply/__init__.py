"""Dedicated auto-apply layer for Career OS.

Consumes an *approved* application package and produces a *structured* result
(SUBMITTED / SUBMISSION_VERIFIED / NEEDS_REVIEW / AUTH_REQUIRED /
BLOCKED_SECURITY_CHALLENGE / UNSUPPORTED / FAILED). The adapter is
portal-aware: it recognises known application flows from the employer URL and
returns UNSUPPORTED when no supported flow maps, rather than guessing or
force-submitting.

The design is informed by the surveyed auto-apply reference projects (AIHawk's
portal abstraction, JustHireMe's supported-vs-experimental model, ai-job-search
and Auto-Company's operator/agent harnesses) but is a native, embeddable
boundary that plugs into the existing approval-gated execution engine - none of
those standalone tools are imported.
"""

from career_os.autoapply.adapter import (
    ApplicationFlow,
    AutoApplyAdapter,
    AutoApplyResult,
    FlowKind,
    build_application_plan,
    detect_application_flow,
)

__all__ = [
    "ApplicationFlow",
    "AutoApplyAdapter",
    "AutoApplyResult",
    "FlowKind",
    "build_application_plan",
    "detect_application_flow",
]
