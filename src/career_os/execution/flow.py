"""Portal/flow classification and plan building for auto-apply.

Lives in the execution package so both the runner and the dedicated
``autoapply`` adapter can consume it without a cross-package import cycle.

The flow classifier recognises known employer application portals (Greenhouse,
Lever, Ashby, Workable, SmartRecruiters, generic application forms) and reports
``UNKNOWN`` (unsupported) otherwise, so nothing is force-submitted on a flow
the adapter cannot drive.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from career_os.execution.engine import ApplicationPlan, Step
from career_os.execution.state import ApplicationExecution


class FlowKind(str, Enum):
    """Recognised application flows that the adapter can drive."""

    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    GENERIC_FORM = "generic_form"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ApplicationFlow:
    """A detected, supported (or unsupported) application flow."""

    kind: FlowKind
    supported: bool
    name: str
    detail: str = ""


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url or "").hostname or "").casefold()


def detect_application_flow(url: str) -> ApplicationFlow:
    """Classify the application flow from an employer application URL."""
    host = _host_of(url)
    path = (url or "").casefold()

    if "greenhouse.io" in host or "boards.greenhouse.io" in host:
        return ApplicationFlow(
            FlowKind.GREENHOUSE, True, "Greenhouse",
            "Greenhouse hosted application form; supported multi-page flow",
        )
    if "lever.co" in host or "jobs.lever.co" in host:
        return ApplicationFlow(
            FlowKind.LEVER, True, "Lever",
            "Lever hosted application form; supported flow",
        )
    if "ashbyhq.com" in host or "jobs.ashbyhq.com" in host:
        return ApplicationFlow(
            FlowKind.ASHBY, True, "Ashby",
            "Ashby hosted application form; supported flow",
        )
    if ".workable.com" in host or "apply.workable.com" in host:
        return ApplicationFlow(
            FlowKind.GENERIC_FORM, True, "Workable",
            "Workable hosted application form; supported flow",
        )
    if ".smartrecruiters.com" in host or "jobs.smartrecruiters.com" in host:
        return ApplicationFlow(
            FlowKind.GENERIC_FORM, True, "SmartRecruiters",
            "SmartRecruiters hosted application form; supported flow",
        )
    if any(marker in path for marker in ("/apply", "/application", "/jobs/", "/careers")):
        return ApplicationFlow(
            FlowKind.GENERIC_FORM, True, "Generic job form",
            "Generic application form; driven with the standard submit flow",
        )
    if "/" in (url or "") and host:
        return ApplicationFlow(
            FlowKind.UNKNOWN, False, "Unknown",
            "Application URL does not map to a supported auto-apply flow",
        )
    return ApplicationFlow(
        FlowKind.UNKNOWN, False, "No application URL",
        "No application URL provided; cannot classify auto-apply flow",
    )


def build_application_plan(execution: ApplicationExecution) -> ApplicationPlan:
    """Build a portal-aware plan for an approved application package."""
    pipeline = execution.pipeline or {}
    url = execution.application_url or ""
    profile = pipeline.get("profile", {}) or {}
    fields = pipeline.get("fields", []) or []

    steps: list[Step] = [Step(kind="open", target=url)]
    for index, field_spec in enumerate(fields):
        key = str(field_spec.get("key", f"field-{index}"))
        input_type = str(field_spec.get("input_type", "text"))
        if input_type == "select":
            steps.append(Step(kind="select", target=key))
        elif input_type == "checkbox":
            steps.append(Step(kind="checkbox", target=key))
        elif input_type == "file":
            steps.append(Step(kind="upload", target=key))
        else:
            steps.append(Step(kind="fill", target=key))
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
