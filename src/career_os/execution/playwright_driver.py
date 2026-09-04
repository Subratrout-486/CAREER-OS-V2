"""Playwright-backed execution driver and runtime driver selection.

The retrieval engine (:mod:`career_os.execution.engine`) is driver-agnostic and
defaults to the deterministic fixture driver so tests and environments without a
real browser never risk contacting an employer. This module adds the real
Playwright driver used for live application execution, selected only when
browser execution is explicitly enabled via ``CAREER_OS_ENABLE_BROWSER=1``.

The driver mirrors the exact step contract of the engine's
``ExecutionDriver`` protocol: each ``step(action, state)`` returns a dict that
may include an updated ``"state"`` plus signal keys the engine consumes
(``error``, ``retryable``, ``validation_error``, ``security_blocked``,
``filled``, ``uploaded``). It returns resolved page text / html / title so the
engine's challenge detection and submission verification logic is the single
source of truth.

Security boundary: this driver never bypasses a CAPTCHA or security challenge.
It only returns page content; the engine classifies any detected challenge as
BLOCKED_SECURITY_CHALLENGE and stops.
"""

from __future__ import annotations

import os
from typing import Any

from career_os.execution.engine import ExecutionDriver


def browser_execution_enabled() -> bool:
    """Return True only when a human has explicitly opted into live browsing.

    Production operators opt in with ``CAREER_OS_ENABLE_BROWSER=1``. Absent that
    flag (the default) the runtime uses the deterministic fixture driver and
    never touches a real site.
    """
    return os.getenv("CAREER_OS_ENABLE_BROWSER", "").strip().casefold() in {"1", "true", "yes"}


def build_driver(*, timeout_ms: int = 30_000) -> ExecutionDriver:
    """Select the runtime driver.

    Returns a :class:`PlaywrightExecutionDriver` when browser execution is
    enabled; otherwise returns the :class:`DeterministicFallbackDriver` which
    replays fixtures offline. A live run is never fabricated when the browser
    is unavailable - the fallback just surfaces an explicit notice.
    """
    if browser_execution_enabled():
        return PlaywrightExecutionDriver(timeout_ms=timeout_ms)
    return DeterministicFallbackDriver()


class PlaywrightExecutionDriver(ExecutionDriver):
    """Real browser driver built on Playwright for approved application fills.

    It fills/selects/uploads fields and advances the application, returning the
    resolved page signals to the engine. Challenge detection and submission
    verification are owned by the engine, not this driver.
    """

    def __init__(self, *, timeout_ms: int = 30_000, headless: bool = True) -> None:
        if not browser_execution_enabled():
            raise RuntimeError(
                "PlaywrightExecutionDriver requires CAREER_OS_ENABLE_BROWSER=1 "
                "to be set; browser execution is disabled by default"
            )
        self.timeout_ms = timeout_ms
        self.headless = headless

    async def step(self, action: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from playwright.async_api import async_playwright

        kind = action.get("kind")
        target = action.get("target", "")
        value = action.get("value")
        url = (
            action.get("target")
            if kind == "open"
            else (state.get("url") or action.get("target", ""))
        )

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=self.headless)
                try:
                    page = await browser.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    if kind in {"open", "nav"}:
                        await page.goto(url, wait_until="domcontentloaded")
                        return {"state": _snapshot(state, page)}
                    if kind == "fill":
                        locator = _locate(page, target)
                        if await locator.count() == 0:
                            return {
                                "state": state,
                                "error": f"field not found: {target}",
                                "retryable": True,
                            }
                        await locator.fill(value or "")
                        return {"state": {**state, "filled": _append(state, "filled", target)}}
                    if kind == "select":
                        locator = _locate(page, target)
                        if value:
                            try:
                                await locator.select_option(label=value)
                            except Exception:  # noqa: BLE001 - fall back to value match
                                await locator.select_option(value)
                        else:
                            await locator.select_option(index=0)
                        return {"state": {**state, "filled": _append(state, "filled", target)}}
                    if kind == "checkbox":
                        locator = _locate(page, target)
                        if value and str(value).casefold() in {"true", "yes", "1"}:
                            await locator.check()
                        return {"state": {**state, "filled": _append(state, "filled", target)}}
                    if kind == "upload":
                        locator = page.locator("input[type='file']").first
                        await locator.set_input_files(target)
                        return {"state": {**state, "uploaded": _append(state, "uploaded", target)}}
                    if kind == "click":
                        locator = page.locator(
                            f"button:has-text('{target}'), input[type='submit'][value='{target}']"
                        ).first
                        if await locator.count() == 0 and target == "submit":
                            locator = page.locator("button[type='submit']").first
                        await locator.click()
                        await page.wait_for_load_state("domcontentloaded")
                        validation = await _detect_validation_label(page)
                        if validation:
                            return {"state": _snapshot(state, page), "validation_error": validation}
                        return {"state": _snapshot(state, page)}
                    if kind == "wait":
                        await page.wait_for_timeout(1000)
                        return {"state": _snapshot(state, page)}
                    if kind == "verify":
                        return {"state": _snapshot(state, page)}
                    return {
                        "state": state,
                        "error": f"unknown step kind {kind!r}",
                        "retryable": False,
                    }
                finally:
                    await browser.close()
        except PlaywrightTimeout as exc:
            return {"state": state, "error": f"browser timeout: {exc}", "retryable": True}
        except Exception as exc:  # noqa: BLE001 - driver must surface any failure to the engine
            return {"state": state, "error": f"browser error: {exc}", "retryable": True}


class DeterministicFallbackDriver(ExecutionDriver):
    """Fallback driver which replays fixtures without a real browser.

    Used whenever browser execution is not enabled. It surfaces an explicit
    notice that no live browsing occurred so a run can never be mistaken for a
    real application.
    """

    def __init__(self) -> None:
        from career_os.execution.engine import DeterministicFixtureDriver

        self._inner = DeterministicFixtureDriver()

    async def step(self, action: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        result = await self._inner.step(action, state)
        if "notice" not in result.get("state", {}):
            result["state"] = {
                **result.get("state", state),
                "notice": "browser execution not enabled; deterministic fixture driver used",
            }
        return result


def _locate(page: Any, key: str) -> Any:
    return page.locator(f"#{key}, [name='{key}']").first


def _append(state: dict[str, Any], key: str, value: str) -> list[str]:
    current = list(state.get(key, []))
    if value not in current:
        current.append(value)
    return current


async def _detect_validation_label(page: Any) -> str | None:
    try:
        text = await page.locator("body").inner_text(timeout=2_000)
    except Exception:  # noqa: BLE001
        return None
    low = text.casefold()
    for marker in ("please fill", "this field is required", "please correct", "please enter"):
        if marker in low:
            return "A required field is missing or invalid"
    return None


def _snapshot(state: dict[str, Any], page: Any) -> dict[str, Any]:
    import re

    html = page.content()
    text = re.sub(r"<[^>]+>", " ", html).strip()
    return {
        **state,
        "page_html": html,
        "page_text": text,
        "page_title": page.title(),
        "url": page.url,
    }
