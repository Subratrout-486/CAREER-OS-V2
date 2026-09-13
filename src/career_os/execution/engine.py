"""Browser application execution engine.

Drives a supported application form through its steps: open URL, map verified
fields, fill multi-page forms, upload resume/supporting docs, answer standard
questions, detect validation errors, retry recoverable failures, capture
evidence, detect the successful submission, and store confirmation.

When a prepared plan carries no field steps (a common gap), the engine
dynamically inspects the opened form, maps discovered controls to *verified*
candidate data, and drives the resulting steps. Unknown/ambiguous required
fields that have no verified answer are never guessed: the run stops and is
reported as a review requirement.

The engine NEVER bypasses a security challenge - if one is detected the
application is classified BLOCKED_SECURITY_CHALLENGE and stopped. A driver
``error`` result is never silently ignored: unrecoverable errors produce an
explicit structured failure result.

The engine is driver-agnostic. A real driver uses Playwright against live
sites; the bundled deterministic driver replays synthetic HTML fixtures for
tests and safe local demos (no real employer is contacted).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from career_os.execution.auth import AuthRequirement, detect_auth_required
from career_os.execution.challenge import ChallengeDetection, detect_challenge

_FIELD_KINDS = {"fill", "select", "checkbox", "upload"}


def _flow_kind(url: str):
    """Best-effort flow classification used to strengthen verification."""
    try:
        from career_os.execution.flow import detect_application_flow

        return detect_application_flow(url).kind
    except ImportError:  # pragma: no cover - defensive against import cycles
        return None


class ExecutionDriver(Protocol):
    async def step(self, action: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class ExecutionResult:
    submitted: bool
    evidence: tuple[str, ...]
    blockers: tuple[str, ...]
    security_blocked: bool = False
    challenge: ChallengeDetection | None = None
    auth_required: bool = False
    auth: AuthRequirement | None = None
    state: str = "unknown"
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class ApplicationExecutionError(Exception):
    pass


@dataclass
class Step:
    kind: str  # open | fill | upload | select | checkbox | click | wait | verify
    target: str = ""
    value: str | None = None
    label: str | None = None


@dataclass
class ApplicationPlan:
    """What the engine should do for one approved application."""

    execution_id: str
    url: str
    profile: dict[str, Any]
    fields: list[dict[str, Any]]
    steps: list[Step]
    resume_path: str | None = None
    support_docs: list[str] = None  # type: ignore[assignment]
    fixture_pages: dict[str, str] | None = None

    def normalized_profile(self) -> dict[str, Any]:
        """Return the verified candidate profile for mapping.

        Prepares callers may store the profile flat (``{first_name: ...}``) or
        nested under ``candidate`` (Source of Truth shape). The mapping layer
        accepts either, but a canonical flat copy is handy and deterministic.
        """
        from career_os.execution.forms import _candidate_value

        profile = dict(self.profile or {})
        cand = profile.get("candidate")
        if isinstance(cand, dict):
            for key, value in cand.items():
                profile.setdefault(key, value)
        return profile

    def resolved_resume_path(self) -> str | None:
        """Return the resume path when the artifact exists; never a fabricated path."""
        if not self.resume_path:
            return None
        path = Path(self.resume_path)
        if path.is_file() and path.stat().st_size > 0:
            return str(path)
        return None


class ApplicationExecutor:
    """Coordinate the deterministic application flow and policy checks.

    A real driver is supplied by the caller. The default deterministic driver
    is used for fixtures/tests. Security challenges always stop the run.
    """

    def __init__(self, driver: ExecutionDriver | None = None, *, max_retries: int = 2) -> None:
        if driver is None:
            from career_os.execution.playwright_driver import build_driver

            driver = build_driver()
        self.driver = driver
        self.max_retries = max_retries

    async def run(
        self,
        *,
        url: str,
        profile: dict[str, Any],
        fields: list[dict[str, Any]],
        steps: list[Step],
        resume_path: str | None = None,
        support_docs: list[str] | None = None,
        fixture_pages: dict[str, str] | None = None,
    ) -> ExecutionResult:
        state: dict[str, Any] = {
            "url": url,
            "profile": profile,
            "fields": fields,
            "resume_path": resume_path,
            "support_docs": support_docs,
            "page_text": "",
            "page_html": "",
            "page_title": "",
            "filled": [],
            "uploaded": [],
            "answered": [],
            "completed_steps": [],
            "nav_step": 0,
        }
        if fixture_pages is not None:
            state["fixture_pages"] = fixture_pages

        # 1. Open the application URL and check for challenge / auth walls.
        opened = await self._do_step({"kind": "open", "target": url}, state)
        if opened.get("error"):
            return self._error_result(url, opened)
        state.update(opened.get("state", {}))
        challenge = detect_challenge(
            url=url,
            text=state.get("page_text", ""),
            html=state.get("page_html", ""),
            title=state.get("page_title", ""),
        )
        if challenge.blocked:
            return self._blocked(url, challenge)
        auth = detect_auth_required(
            url=url,
            text=state.get("page_text", ""),
            html=state.get("page_html", ""),
            title=state.get("page_title", ""),
        )
        if auth.required:
            return self._auth_required(url, auth)

        # 2. If the plan carries no explicit field steps, dynamically inspect the
        #    opened form and map its controls to verified candidate data.
        effective_steps = list(steps)
        has_field_steps = any(step.kind in _FIELD_KINDS for step in effective_steps)
        if not has_field_steps and state.get("page_html"):
            mapped = self._build_discovery_steps(
                page_html=state["page_html"],
                profile=profile,
                resume_path=resume_path,
                fields=fields,
            )
            if mapped["review"]:
                return self._needs_review(url, mapped["review"])
            effective_steps = mapped["steps"]
            state["field_discovery"] = mapped["discovery"]
            state["skipped_optional"] = mapped["skipped_optional"]

        # 3. Run the application steps in order with bounded retries.
        for step in effective_steps:
            outcome = await self._run_step_with_retry(step, state)
            if not outcome:
                return self._error_result(url, {"error": "step failed after retries", "retryable": False})
            if outcome.get("error") and not outcome.get("retryable"):
                return self._error_result(url, outcome)
            if outcome.get("security_blocked"):
                ch = outcome.get("challenge")
                return self._blocked(url, ch)
            if outcome.get("auth_required"):
                auth_result = outcome.get("auth")
                return self._auth_required(url, auth_result)
            if outcome.get("validation_error"):
                return ExecutionResult(
                    submitted=False,
                    evidence=(),
                    blockers=(str(outcome["validation_error"]),),
                    state="validation_error",
                    reason=str(outcome["validation_error"]),
                    details={"step": step.kind, "target": step.target},
                )
            state.update(outcome.get("state", {}))
            state["completed_steps"].append(asdict(step))
            # The live driver already records filled/uploaded targets in the state
            # it returns; only record here when a driver did not (e.g. fixtures).
            if step.kind in {"fill", "upload", "select", "checkbox"} and step.target:
                bucket = "uploaded" if step.kind == "upload" else "filled"
                if step.target not in state.get(bucket, []):
                    state[bucket].append(step.target)

        # 4. Attempt to advance to / read the result page and verify submission.
        #    The plan's own verify step already captured the final page and closed
        #    the browser session; a redundant verify against a closed session is a
        #    driver error that must not be treated as a submission failure.
        verify_steps = [step for step in effective_steps if step.kind == "verify"]
        if verify_steps:
            final: dict[str, Any] = {"state": state}
            # A plan may name the confirmation URL as the verify target. Promote
            # that transition so evidence reflects the post-submit page rather
            # than the original apply URL.
            verify_target = verify_steps[-1].target
            if verify_target and "://" in verify_target:
                state["url"] = verify_target
        else:
            final = await self._do_step({"kind": "verify", "target": url}, state)
            if final.get("error"):
                return self._error_result(url, final)
        state.update(final.get("state", {}))
        page_text = state.get("page_text", "")
        challenge = detect_challenge(
            url=url,
            text=page_text,
            html=state.get("page_html", ""),
            title=state.get("page_title", ""),
        )
        if challenge.blocked:
            return self._blocked(url, challenge)
        auth = detect_auth_required(
            url=url,
            text=page_text,
            html=state.get("page_html", ""),
            title=state.get("page_title", ""),
        )
        if auth.required:
            return self._auth_required(url, auth)

        # Portal-aware verification strengthens plain text detection: known
        # portals (Greenhouse, Lever, Ashby, Workable, SmartRecruiters) have
        # recognisable confirmation markers and success URL transitions.
        portal_confirmed = False
        portal_reference: str | None = None
        flow_kind = _flow_kind(url)
        if flow_kind is not None:
            try:
                from career_os.execution.portals import apply_portal_heuristics
            except ImportError:  # pragma: no cover - defensive
                portal_confirmed, portal_reference = False, None
            else:
                portal_confirmed, portal_reference = apply_portal_heuristics(
                    flow_kind=flow_kind,
                    page_text=page_text,
                    page_title=state.get("page_title", ""),
                    url=state.get("url", url),
                )

        submitted = _looks_submitted(page_text) or portal_confirmed
        evidence = _extract_evidence(state, page_text, url, portal_reference) if submitted else ()

        if submitted and not evidence:
            return ExecutionResult(
                submitted=False,
                evidence=(),
                blockers=("Submission observed without confirmation evidence"),
                state="missing_evidence",
                reason="Confirmation evidence could not be extracted",
                details={"page_text": page_text[:500]},
            )

        # A submit control was clicked but no confirmation signal appeared.
        # The click happened and the application may or may not have been
        # received: never report a verified success, but persist the action so
        # the runner can record an unverified (human-review) submission state.
        if not submitted and "click" in {step.kind for step in effective_steps}:
            return ExecutionResult(
                submitted=True,
                evidence=(),
                blockers=("Submit action occurred but no authoritative confirmation was observed"),
                state="submission_unverified",
                reason="Application may or may not have been received; confirmation not verified",
                details={
                    "filled": state.get("filled", []),
                    "uploaded": state.get("uploaded", []),
                    "page_title": state.get("page_title", ""),
                },
            )

        return ExecutionResult(
            submitted=submitted,
            evidence=evidence,
            blockers=() if submitted else ("No successful submission signal observed",),
            state="submitted" if submitted else "not_submitted",
            details={
                "filled": state.get("filled", []),
                "uploaded": state.get("uploaded", []),
                "answered": state.get("answered", []),
                "page_title": state.get("page_title", ""),
                "skipped_optional": state.get("skipped_optional", []),
                "field_discovery": state.get("field_discovery", []),
            },
        )

    def _build_discovery_steps(
        self,
        *,
        page_html: str,
        profile: dict[str, Any],
        resume_path: str | None,
        fields: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Inspect the opened form and produce a safe, verified step list.

        The existing plan may already carry a ``fields`` list (from preparation);
        it is used as the primary control description. Otherwise the form is
        discovered from the live page snapshot. Any required field the mapper
        cannot resolve from verified data returns a review blocker.
        """
        from career_os.execution.forms import (
            discover_fields,
            map_discovered_fields,
        )

        if fields:
            mapped = _map_plan_fields(fields, profile)
        else:
            discovered = discover_fields(page_html)
            mapped = map_discovered_fields(discovered, profile)

        steps: list[Step] = []
        review: list[str] = []
        skipped_optional: list[str] = []
        resume = _resolve_resume_path(resume_path)
        for mapping in mapped:
            if mapping.field.input_type == "file":
                # A resume/cv file input is resolved by the tailored resume
                # artifact, not by the Source of Truth profile. Without a valid
                # artifact there is nothing safe to upload.
                if mapping.field.value_hint == "resume" and resume:
                    steps.append(
                        Step(
                            kind="upload",
                            target=mapping.field.key,
                            value=resume,
                            label=mapping.field.label or "resume",
                        )
                    )
                elif mapping.field.required:
                    review.append(f"{mapping.field.label or mapping.field.key}: no resume artifact available to upload")
                else:
                    skipped_optional.append(mapping.field.key)
                continue
            if mapping.resolved:
                kind = _step_kind_for(mapping.field.input_type)
                steps.append(
                    Step(
                        kind=kind,
                        target=mapping.field.key,
                        value=mapping.value,
                        label=mapping.field.label or None,
                    )
                )
            elif mapping.review:
                review.append(f"{mapping.field.label or mapping.field.key}: {mapping.reason or 'no verified value'}")
            elif mapping.optional:
                skipped_optional.append(mapping.field.key)

        if review:
            return {"review": review, "steps": steps, "discovery": [], "skipped_optional": skipped_optional}

        steps.append(Step(kind="click", target="submit"))
        steps.append(Step(kind="wait"))
        steps.append(Step(kind="verify"))
        return {
            "review": [],
            "steps": steps,
            "discovery": [
                {
                    "field": {
                        "key": m.field.key,
                        "input_type": m.field.input_type,
                        "label": m.field.label,
                        "required": m.field.required,
                        "options": list(m.field.options),
                    },
                    "concept": m.concept,
                    "value": m.value,
                    "resolved": m.resolved,
                    "optional": m.optional,
                    "review": m.review,
                    "reason": m.reason,
                }
                for m in mapped
            ],
            "skipped_optional": skipped_optional,
        }

    async def _do_step(self, action: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        return await self.driver.step(action, state)

    async def _run_step_with_retry(self, step: Step, state: dict[str, Any]) -> dict[str, Any]:
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            outcome = await self._do_step(asdict(step), state)
            if outcome.get("error") and outcome.get("retryable"):
                last_error = str(outcome["error"])
                continue
            if outcome.get("security_blocked"):
                break
            return outcome
        return {"error": last_error or "step failed after retries", "retryable": False}

    def _blocked(self, url: str, challenge: ChallengeDetection) -> ExecutionResult:
        return ExecutionResult(
            submitted=False,
            evidence=(),
            blockers=(challenge.detail,),
            security_blocked=True,
            challenge=challenge,
            state="blocked_security_challenge",
            reason=challenge.detail,
            details={"signals": list(challenge.signals)},
        )

    def _auth_required(self, url: str, auth: AuthRequirement) -> ExecutionResult:
        return ExecutionResult(
            submitted=False,
            evidence=(),
            blockers=(auth.detail,),
            auth_required=True,
            auth=auth,
            state="auth_required",
            reason=auth.detail,
            details={"signals": list(auth.signals)},
        )

    def _error_result(self, url: str, outcome: dict[str, Any]) -> ExecutionResult:
        """Never silently ignore a browser/driver error."""
        message = str(outcome.get("error") or "unrecoverable driver error")
        return ExecutionResult(
            submitted=False,
            evidence=(),
            blockers=(message,),
            state="error",
            reason=message,
            details={
                "url": url,
                "retryable": bool(outcome.get("retryable")),
                "step_error": True,
            },
        )

    def _needs_review(self, url: str, review: list[str]) -> ExecutionResult:
        return ExecutionResult(
            submitted=False,
            evidence=(),
            blockers=tuple(review),
            state="needs_review",
            reason="Required application fields could not be answered from verified candidate data",
            details={"url": url, "review_fields": list(review)},
        )


def _step_kind_for(input_type: str) -> str:
    kind = input_type.casefold()
    if kind == "select":
        return "select"
    if kind == "checkbox":
        return "checkbox"
    if kind == "file":
        return "upload"
    if kind == "radio":
        return "checkbox"
    return "fill"


def _map_plan_fields(fields: list[dict[str, Any]], profile: dict[str, Any]):
    """Map explicit plan field descriptors through the verified mapping layer."""
    from career_os.execution.forms import FormField, map_discovered_fields

    discovered = [
        FormField(
            key=str(f.get("key", f"field-{i}")),
            input_type=str(f.get("input_type", "text")),
            label=str(f.get("label", "")),
            placeholder=str(f.get("placeholder", "")),
            aria_label=str(f.get("aria_label", "")),
            required=bool(f.get("required", False)),
            options=tuple(str(o) for o in (f.get("options") or []) if o),
        )
        for i, f in enumerate(fields)
    ]
    return map_discovered_fields(discovered, profile)


def _resolve_resume_path(resume_path: str | None) -> str | None:
    if not resume_path:
        return None
    path = Path(resume_path)
    if path.is_file() and path.stat().st_size > 0:
        return str(path)
    return None


def _looks_submitted(text: str) -> bool:
    import re

    low = text.casefold()
    if re.search(
        r"(?:application|submission)\s+(?:has\s+been\s+|was\s+|is\s+)?(?:successfully\s+)?(?:submitted|received|complete)",
        low,
    ):
        return True
    ok = (
        "application submitted" in low,
        "thank you" in low and "application" in low,
        "we have received your application" in low,
        "successfully applied" in low,
        "application received" in low,
        "application complete" in low,
        "submission received" in low,
    )
    return any(ok)


def _extract_evidence(
    state: dict[str, Any], page_text: str, url: str, portal_reference: str | None = None
) -> tuple[str, ...]:
    import re

    evidence = [f"observed successful submission signal on {state.get('url', url)}"]
    references = re.findall(
        r"(?:reference|confirmation|application|ref)(?:\s+(?:id|number|ref))?\s*[:#]?\s*"
        r"([A-Z0-9][A-Z0-9\-_]{2,25})",
        page_text,
        re.IGNORECASE,
    )
    tokens = [portal_reference] if portal_reference else []
    tokens.extend(
        token
        for token in references
        # Identifier-like tokens contain a digit or are fully uppercase; words
        # like "has" / "received" from the prose are not references.
        if re.search(r"\d", token) or token.isupper()
    )
    if tokens:
        evidence.append(f"reference: {tokens[0]}")
    filled = state.get("filled", [])
    if filled:
        evidence.append(f"fields filled: {', '.join(filled)}")
    uploaded = state.get("uploaded", [])
    if uploaded:
        evidence.append(f"documents uploaded: {', '.join(uploaded)}")
    return tuple(dict.fromkeys(evidence))


class DeterministicFixtureDriver:
    """Replay synthetic HTML fixtures locally - never touches real employers.

    Pages are plain HTML passed via state['fixture_pages']. The driver walks
    requested steps, records fills/uploads, detects validation errors and
    security challenges, and returns a submission page per the fixture.
    """

    def __init__(self, fixture_root: Path | None = None) -> None:
        self.fixture_root = fixture_root

    async def step(self, action: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        kind = action.get("kind")
        pages = state.get("fixture_pages", {})
        nav_step = state.get("nav_step", 0)

        if kind == "open":
            html = _page_for(state, pages, nav_step)
            return {"state": _inject_page(state, html, nav_step)}

        if kind == "verify":
            html = _page_for(state, pages, len(pages) - 1)
            return {"state": _inject_page(state, html, len(pages) - 1)}

        if kind == "fill":
            return {"state": state, "filled": True}

        if kind == "upload":
            return {"state": state, "uploaded": True}

        if kind == "select" or kind == "checkbox":
            return {"state": state}

        if kind == "click":
            nav_step += 1
            html = _page_for(state, pages, nav_step)
            state["nav_step"] = nav_step
            validation = _detect_validation(html)
            if validation:
                return {"state": state, "validation_error": validation}
            return {"state": state, "ok": True}

        if kind == "wait":
            return {"state": state}

        return {"state": state, "error": f"unknown step kind {kind!r}", "retryable": False}


def _page_for(state: dict[str, Any], pages: dict[str, Any], index: int) -> str:
    callback = state.get("page_callback")
    if callable(callback):
        return callback(index)
    if not pages:
        return "<html><body>fixture</body></html>"
    # Fixture pages are positional by insertion order. Authors may name pages;
    # the "open"/"apply"/"start"/"form" key (when present) is always the first
    # navigation, and every later step advances through the remaining keys.
    keys = list(pages.keys())
    if index == 0:
        preferred = next((k for k in ("open", "apply", "start", "form") if k in pages), keys[0])
        return pages[preferred]
    return pages[keys[min(index, len(keys) - 1)]]


def _inject_page(state: dict[str, Any], html: str, nav_step: int) -> dict[str, Any]:
    import html as html_mod
    import re

    text = re.sub(r"<[^>]+>", " ", html)
    text = html_mod.unescape(text)
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return {
        **state,
        "page_html": html,
        "page_text": text,
        "page_title": title.group(1) if title else "",
        "nav_step": nav_step,
    }


def _detect_validation(html: str) -> str | None:
    import re

    for pattern in (
        re.compile(r"class=[\"'][^\"']*(?:error|invalid|required)[^\"']*[\"']", re.IGNORECASE),
        re.compile(
            r">\s*(?:please (?:fill|correct|enter|provide)|this field is required)\s*<",
            re.IGNORECASE,
        ),
    ):
        if pattern.search(html):
            return "A required field is missing or invalid"
    return None
