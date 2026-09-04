"""Real Playwright-backed driver for the application execution engine.

This driver drives live sites only after an application is APPROVED. It
inspects the running form, fills verified fields, uploads documents, clicks
through steps, captures textual evidence, and detects security challenges.

It NEVER attempts to solve or bypass a CAPTCHA / bot challenge. When one is
detected the driver returns a security_blocked outcome and stops.
"""

from __future__ import annotations

from typing import Any

from career_os.execution.engine import (
    _detect_validation,
    _looks_submitted,
)
from career_os.models.resume import ResumeProfile


class PlaywrightApplicationDriver:
    """Minimal Playwright driver. Launch real browsers only when configured."""

    def __init__(self, *, headless: bool = True, session_cookies: list[dict[str, Any]] | None = None) -> None:
        self.headless = headless
        self.session_cookies = session_cookies or []

    async def step(self, action: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        from playwright.async_api import async_playwright

        from career_os.execution.challenge import detect_challenge

        kind = action.get("kind")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            if self.session_cookies:
                await context.add_cookies(self.session_cookies)
            page = await context.new_page()
            url = action.get("target") or state.get("url", "")

            if kind == "open":
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            elif kind == "fill":
                key = action.get("target", "")
                value = action.get("value")
                if value is None:
                    value = _profile_value(state.get("profile", {}), key)
                locator = page.locator(f"#{key}, [name='{key}'], [id='{key}']").first
                if await locator.count() == 0:
                    return {"state": state, "error": f"field {key!r} not found", "retryable": False}
                await locator.fill(str(value))
            elif kind == "select":
                key = action.get("target", "")
                value = action.get("value") or _profile_value(state.get("profile", {}), key)
                locator = page.locator(f"#{key}, [name='{key}']").first
                if await locator.count() == 0:
                    return {"state": state, "error": f"field {key!r} not found", "retryable": False}
                await locator.select_option(label=str(value))
            elif kind == "checkbox":
                key = action.get("target", "")
                value = action.get("value")
                locator = page.locator(f"#{key}, [name='{key}']").first
                if await locator.count() == 0:
                    return {"state": state, "error": f"field {key!r} not found", "retryable": False}
                if str(value or _profile_value(state.get("profile", {}), key)).casefold() in {"true", "yes", "1"}:
                    await locator.check()
            elif kind == "upload":
                path = action.get("value") or state.get("resume_path")
                locator = page.locator("input[type='file']").first
                if await locator.count() == 0:
                    return {"state": state, "error": "no file input found", "retryable": False}
                await locator.set_input_files(path)
            elif kind == "click":
                target = action.get("target", "submit")
                locator = page.locator(f"button[type='submit'], input[type='submit'], a:has-text('{target}')").first
                if await locator.count() == 0:
                    return {"state": state, "error": "submit control not found", "retryable": False}
                await locator.click()
            elif kind == "wait":
                await page.wait_for_timeout(1500)
            elif kind == "verify":
                pass

            await page.wait_for_load_state("domcontentloaded")
            text = await page.evaluate("document.body ? document.body.innerText : ''")
            html = await page.evaluate("document.documentElement ? document.documentElement.outerHTML : ''")
            title = await page.title()

            challenge = detect_challenge(url=url, text=text, html=html, title=title)
            if challenge.blocked:
                await browser.close()
                return {"state": state, "security_blocked": True, "challenge": challenge}

            validation = _detect_validation(html)
            await browser.close()
            return {
                "state": {
                    **state,
                    "page_text": text,
                    "page_html": html,
                    "page_title": title,
                },
                "ok": True,
                "validation_error": validation,
                "submitted_lookup": _looks_submitted(text),
            }


def _profile_value(profile: dict[str, Any], key: str) -> str:
    import re

    norm = re.sub(r"[^a-z0-9]+", " ", key.casefold()).strip()
    for profile_key, value in profile.items():
        if norm in re.sub(r"[^a-z0-9]+", " ", str(profile_key).casefold()):
            return str(value)
    return ""


def resume_profile_to_dict(profile: ResumeProfile) -> dict[str, Any]:
    return {
        "summary": profile.summary,
        "bullets": [
            {"text": b.text, "evidence_claim_ids": list(b.evidence_claim_ids)}
            for b in profile.bullets
        ],
    }
