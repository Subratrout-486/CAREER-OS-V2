"""Browser application execution engine.

Drives a supported application form through its steps: open URL, map verified
fields, fill multi-page forms, upload resume/supporting docs, answer standard
questions, detect validation errors, retry recoverable failures, capture
evidence, detect the successful submission, and store confirmation.

The engine NEVER bypasses a security challenge - if one is detected the
application is classified BLOCKED_SECURITY_CHALLENGE and stopped.

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

        # 2. Run the application steps in order with bounded retries.
        for step in steps:
            outcome = await self._run_step_with_retry(step, state)
            if outcome.get("security_blocked"):
                ch = outcome.get("challenge")
                return self._blocked(url, ch)
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
            if step.kind in {"fill", "upload", "select", "checkbox"} and step.target:
                if step.kind in {"upload"}:
                    state["uploaded"].append(step.target)
                elif step.kind in {"select", "checkbox", "fill"}:
                    state["filled"].append(step.target)

        # 3. Attempt to advance to / read the result page and verify submission.
        final = await self._do_step({"kind": "verify", "target": url}, state)
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

        submitted = _looks_submitted(page_text)
        evidence = _extract_evidence(state, page_text, url) if submitted else ()

        if submitted and not evidence:
            return ExecutionResult(
                submitted=False,
                evidence=(),
                blockers=("Submission observed without confirmation evidence"),
                state="missing_evidence",
                reason="Confirmation evidence could not be extracted",
                details={"page_text": page_text[:500]},
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
            },
        )

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


def _extract_evidence(state: dict[str, Any], page_text: str, url: str) -> tuple[str, ...]:
    import re

    evidence = [f"observed successful submission signal on {url}"]
    m = re.search(
        r"(?:reference|confirmation|application)\s*(?:id|number|ref)\s*[:#]?\s*([A-Za-z0-9\-_]+)",
        page_text,
        re.IGNORECASE,
    )
    if m:
        evidence.append(f"reference: {m.group(1)}")
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
    # Direct fixture page ordered by key or by index.
    if pages:
        keys = sorted(pages.keys())
        key = keys[min(index, len(keys) - 1)]
        return pages[key]
    return "<html><body>fixture</body></html>"


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
