"""Playwright-backed execution driver and runtime driver selection.

The driver keeps one browser/page session alive for the complete application
flow. The previous implementation launched a fresh Chromium process for every
step, which discarded form state between ``open``/``fill``/``click``/``verify``
and made a real multi-step application impossible.

A live run may either launch local Chromium or attach to an already-running
Chromium endpoint through ``APPLICATION_BROWSER_CDP_URL``. The latter is the
integration point for controlled remote browsers such as Fortress. Playwright
remains the automation API in both cases.

Security boundary: this driver never bypasses a CAPTCHA or security challenge.
It only returns page content; the engine classifies any detected challenge as
BLOCKED_SECURITY_CHALLENGE and stops.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from career_os.execution.engine import ExecutionDriver


def browser_execution_enabled() -> bool:
    """Return True only when a human has explicitly opted into live browsing."""
    return os.getenv("CAREER_OS_ENABLE_BROWSER", "").strip().casefold() in {
        "1",
        "true",
        "yes",
    }


def build_driver(*, timeout_ms: int = 30_000) -> ExecutionDriver:
    """Select the runtime driver.

    A CDP URL takes precedence over local Chromium when browser execution is
    enabled. This allows a persistent or remote browser to be controlled with
    the same Playwright automation layer.
    """
    if browser_execution_enabled():
        return PlaywrightExecutionDriver(timeout_ms=timeout_ms)
    return DeterministicFallbackDriver()


class PlaywrightExecutionDriver(ExecutionDriver):
    """Real browser driver for approved application fills.

    The driver is intentionally stateful for one application attempt. It starts
    Playwright/browser on the first ``open`` action and reuses the same page for
    every subsequent action. The session is closed on ``verify`` or when an
    unexpected error occurs.
    """

    def __init__(self, *, timeout_ms: int = 30_000, headless: bool | None = None) -> None:
        if not browser_execution_enabled():
            raise RuntimeError(
                "PlaywrightExecutionDriver requires CAREER_OS_ENABLE_BROWSER=1 "
                "to be set; browser execution is disabled by default"
            )
        self.timeout_ms = timeout_ms
        if headless is None:
            self.headless = os.getenv("APPLICATION_BROWSER_HEADLESS", "1").strip().casefold() not in {
                "0",
                "false",
                "no",
            }
        else:
            self.headless = headless
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._connected_over_cdp = False

    async def step(self, action: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from playwright.async_api import async_playwright

        kind = action.get("kind")
        target = action.get("target", "")
        value = action.get("value")

        try:
            if kind == "open":
                await self._ensure_session()
                assert self._page is not None
                self._page.set_default_timeout(self.timeout_ms)
                await self._page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)
                return {"state": await _snapshot_async(state, self._page)}

            if self._page is None:
                return {
                    "state": state,
                    "error": "browser session is not open; application must begin with open",
                    "retryable": False,
                }

            page = self._page
            page.set_default_timeout(self.timeout_ms)

            if kind in {"nav"}:
                await page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)
                return {"state": await _snapshot_async(state, page)}

            if kind == "fill":
                locator = await _locate(page, target)
                if await locator.count() == 0:
                    return {
                        "state": state,
                        "error": f"field not found: {target}",
                        "retryable": True,
                    }
                await locator.fill(value or "")
                return {"state": {**state, "filled": _append(state, "filled", target)}}

            if kind == "select":
                locator = await _locate(page, target)
                if await locator.count() == 0:
                    return {
                        "state": state,
                        "error": f"field not found: {target}",
                        "retryable": True,
                    }
                if value:
                    try:
                        await locator.select_option(label=value)
                    except Exception:  # noqa: BLE001 - fall back to value match
                        await locator.select_option(value=value)
                else:
                    await locator.select_option(index=0)
                return {"state": {**state, "filled": _append(state, "filled", target)}}

            if kind == "checkbox":
                locator = await _locate(page, target)
                if await locator.count() == 0:
                    return {
                        "state": state,
                        "error": f"field not found: {target}",
                        "retryable": True,
                    }
                if value and str(value).casefold() in {"true", "yes", "1"}:
                    await locator.check()
                return {"state": {**state, "filled": _append(state, "filled", target)}}

            if kind == "upload":
                file_value = value or target
                if not file_value or not _path_exists(file_value):
                    return {
                        "state": state,
                        "error": f"resume artifact does not exist: {file_value}",
                        "retryable": False,
                    }
                locator = await _locate(page, target)
                if await locator.count() == 0:
                    locator = page.locator("input[type='file']").first
                if await locator.count() == 0:
                    return {
                        "state": state,
                        "error": "no file input found on the page",
                        "retryable": False,
                    }
                await locator.set_input_files(file_value)
                return {"state": {**state, "uploaded": _append(state, "uploaded", target)}}

            if kind == "click":
                locator = await _submit_locator(page, target)
                if await locator.count() == 0:
                    return {
                        "state": await _snapshot_async(state, page),
                        "error": f"unambiguous submit control not found: {target}",
                        "retryable": False,
                    }
                await locator.click()
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=min(self.timeout_ms, 10_000))
                except PlaywrightTimeout:
                    # Some ATS forms submit through XHR and do not navigate.
                    pass
                validation = await _detect_validation_label(page)
                if validation:
                    return {"state": await _snapshot_async(state, page), "validation_error": validation}
                return {"state": await _snapshot_async(state, page)}

            if kind == "wait":
                await page.wait_for_timeout(1000)
                return {"state": await _snapshot_async(state, page)}

            if kind == "verify":
                result = {"state": await _snapshot_async(state, page)}
                await self.close()
                return result

            return {
                "state": state,
                "error": f"unknown step kind {kind!r}",
                "retryable": False,
            }
        except PlaywrightTimeout as exc:
            await self.close()
            return {"state": state, "error": f"browser timeout: {exc}", "retryable": False}
        except Exception as exc:  # noqa: BLE001 - driver must surface failures to the engine
            await self.close()
            return {"state": state, "error": f"browser error: {exc}", "retryable": False}

    async def _ensure_session(self) -> None:
        if self._page is not None:
            return

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        cdp_url = os.getenv("APPLICATION_BROWSER_CDP_URL", "").strip()
        if cdp_url:
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            self._connected_over_cdp = True
            self._context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            return

        profile_dir = os.getenv("APPLICATION_BROWSER_PROFILE", "").strip()
        if profile_dir:
            self._context = await self._playwright.chromium.launch_persistent_context(
                profile_dir,
                headless=self.headless,
            )
            self._browser = None
        else:
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context()
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

    async def close(self) -> None:
        """Close the local automation session without deleting remote browser state."""
        try:
            if self._context is not None and not self._connected_over_cdp:
                await self._context.close()
            elif self._browser is not None and self._connected_over_cdp:
                # Disconnect from a remote browser; do not intentionally shut it down.
                await self._browser.close()
        finally:
            if self._playwright is not None:
                await self._playwright.stop()
            self._playwright = None
            self._browser = None
            self._context = None
            self._page = None
            self._connected_over_cdp = False


class DeterministicFallbackDriver(ExecutionDriver):
    """Fallback driver which replays fixtures without a real browser."""

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


async def _locate(page: Any, key: str) -> Any:
    """Locate a form control by stable id/name first, then label/aria signal.

    ``key`` is a deterministic key generated by the plan builder / form mapper,
    so no external label text is ever interpolated into a CSS selector.
    """
    escaped = str(key).replace("'", "\\'")
    by_id = page.locator(f"#{escaped}")
    if await by_id.count() > 0:
        return by_id.first
    by_name = page.locator(f"[name='{escaped}']")
    if await by_name.count() > 0:
        return by_name.first
    # Semantic fallbacks: a label whose for/text matches the key, or an
    # aria-label / placeholder that contains the key.
    labelled = page.locator(f"label:has-text('{escaped}') + input, label:has-text('{escaped}') + textarea, label:has-text('{escaped}') + select")
    if await labelled.count() > 0:
        return labelled.first
    aria = page.locator(f"[aria-label*='{escaped}'], [placeholder*='{escaped}']").first
    return aria


def _path_exists(value: str | None) -> bool:
    if not value:
        return False
    try:
        return Path(value).is_file() and Path(value).stat().st_size > 0
    except OSError:
        return False


async def _submit_locator(page: Any, target: str) -> Any:
    """Find the submit control, preferring the smallest unambiguous match.

    The generic fallback is ordered most-specific first (submit buttons labelled
    Submit/Apply) and only falls back to any visible ``[type=submit]`` element,
    so a populated form never silently matches a hidden secondary control.
    """
    if target != "submit":
        return page.locator(
            f"button:has-text('{str(target).replace(chr(39), chr(92)+chr(39))}'), "
            f"input[type='submit'][value='{str(target).replace(chr(39), chr(92)+chr(39))}']"
        ).first
    candidates = page.locator(
        "button[type='submit']:has-text('Submit application'), "
        "button[type='submit']:has-text('Submit'), "
        "input[type='submit'][value*='Submit'], "
        "button[type='submit']:has-text('Apply Now'), "
        "button[type='submit']:has-text('Apply'), "
        "input[type='submit'][value*='Apply']"
    )
    visible_present = False
    try:
        visible_present = await candidates.filter(visible=True).count() > 0
    except Exception:  # noqa: BLE001 - a non-visible match simply falls through
        visible_present = False
    if visible_present:
        return candidates.filter(visible=True).first
    return page.locator("button[type='submit'], input[type='submit']").filter(visible=True).first


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


async def _snapshot_async(state: dict[str, Any], page: Any) -> dict[str, Any]:
    import re

    html = await page.content()
    text = re.sub(r"<[^>]+>", " ", html).strip()
    return {
        **state,
        "page_html": html,
        "page_text": text,
        "page_title": await page.title(),
        "url": page.url,
    }
