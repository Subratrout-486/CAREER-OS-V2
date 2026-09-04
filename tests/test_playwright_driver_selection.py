"""Tests for browser runtime driver selection.

These must pass in an environment WITHOUT Chromium/Playwright installed. They
verify that live browser execution is off by default, that the safe
deterministic fallback is used, and that the Playwright driver refuses to run
unless explicitly enabled. No real employer is ever contacted.
"""

from __future__ import annotations

import asyncio

import pytest

from career_os.execution.engine import ApplicationExecutor, DeterministicFixtureDriver
from career_os.execution.playwright_driver import (
    DeterministicFallbackDriver,
    PlaywrightExecutionDriver,
    browser_execution_enabled,
    build_driver,
)


def _run(coro):
    return asyncio.run(coro)


def test_browser_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CAREER_OS_ENABLE_BROWSER", raising=False)
    assert browser_execution_enabled() is False


def test_browser_enabled_flag(monkeypatch):
    monkeypatch.setenv("CAREER_OS_ENABLE_BROWSER", "1")
    assert browser_execution_enabled() is True
    monkeypatch.setenv("CAREER_OS_ENABLE_BROWSER", "true")
    assert browser_execution_enabled() is True
    monkeypatch.setenv("CAREER_OS_ENABLE_BROWSER", "0")
    assert browser_execution_enabled() is False


def test_playwright_driver_refuses_when_disabled(monkeypatch):
    monkeypatch.delenv("CAREER_OS_ENABLE_BROWSER", raising=False)
    with pytest.raises(RuntimeError):
        PlaywrightExecutionDriver()


def test_build_driver_returns_safe_fallback_when_disabled(monkeypatch):
    monkeypatch.delenv("CAREER_OS_ENABLE_BROWSER", raising=False)
    driver = build_driver()
    # It must NOT be the real browser driver; a live run is never attempted.
    assert not isinstance(driver, PlaywrightExecutionDriver)


def test_deterministic_fallback_runs_fixture_and_notes_no_browser(monkeypatch):
    monkeypatch.delenv("CAREER_OS_ENABLE_BROWSER", raising=False)
    driver = build_driver()
    result = _run(
        driver.step(
            {"kind": "open", "target": "https://example.test/job"},
            {
                "url": "https://example.test/job",
                "fixture_pages": {"0": "<html><body>apply now</body></html>"},
            },
        )
    )
    assert "notice" in result["state"]
    assert "browser execution not enabled" in result["state"]["notice"]


def test_executor_defaults_to_safe_driver(monkeypatch):
    monkeypatch.delenv("CAREER_OS_ENABLE_BROWSER", raising=False)
    executor = ApplicationExecutor()
    # The engine default is a deterministic driver - a live browser run is never
    # attempted unless browser execution is explicitly enabled.
    assert isinstance(executor.driver, (DeterministicFixtureDriver, DeterministicFallbackDriver))
    assert not isinstance(executor.driver, PlaywrightExecutionDriver)
