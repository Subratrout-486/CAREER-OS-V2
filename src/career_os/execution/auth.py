"""Authentication-required detection for the application engine.

Distinguishes a login/authentication wall from a security challenge and from a
generic submission failure. A page that requires the user to sign in before it
will accept an application must be reported as authentication-required and
paused for the human - never recorded as a successful submission and never
conflated with a CAPTCHA/bot-detection block.

This module only DETECTS the requirement to authenticate. It contains no logic
to obtain, store, or reuse credentials and performs no login on any site.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_SIGNAL_PATTERNS = (
    re.compile(r"\bsign\s?in\b", re.IGNORECASE),
    re.compile(r"\blog\s?in\b", re.IGNORECASE),
    re.compile(r"\blog\s?on\b", re.IGNORECASE),
    re.compile(r"you must (?:be )?(?:signed|logged|log) in", re.IGNORECASE),
    re.compile(r"please (?:sign|log) in", re.IGNORECASE),
    re.compile(r"authentication required", re.IGNORECASE),
    re.compile(r"login required", re.IGNORECASE),
    re.compile(r"you are not authenticated", re.IGNORECASE),
    re.compile(r"session (?:has )?expired", re.IGNORECASE),
)

# Form/input markers that indicate an interactive login form on the page.
_LOGIN_FORM_SIGNALS = (
    r"type=[\"']password[\"']",
    r"placeholder=[\"'][^\"']*password[\"']",
    r">\s*password\s*<",
    r">\s*sign in\s*<",
    r">\s*log in\s*<",
)

_DECLARATIVE_EXCLUDE = (
    "forgot password",
    "reset password",
    "create a password",
    "new password",
    "change your password",
)

# Auth walls that are passive require-login q-nodes; these never indicate
# "already authenticated".
_URL_HINTS = (
    "/login",
    "/signin",
    "/sign-in",
    "/auth/login",
)


@dataclass(frozen=True)
class AuthRequirement:
    """Result of scanning a page for a requirement to authenticate."""

    url: str
    required: bool
    signals: tuple[str, ...] = field(default_factory=tuple)
    detail: str = ""


def detect_auth_required(
    *,
    url: str,
    text: str = "",
    html: str = "",
    title: str = "",
    http_status: int | None = None,
) -> AuthRequirement:
    """Detect a login/authentication wall from browser page signals.

    Returns a structured result; the caller must pause the application for
    human authentication rather than proceeding or reporting success.
    """
    combined_text = f"{title} {text}"
    haystack = f"{combined_text} {html} {url}"
    low = haystack.casefold()

    signals: list[str] = []

    for pattern in _SIGNAL_PATTERNS:
        if pattern.search(haystack):
            signals.append(pattern.pattern)
            break

    if http_status == 401 or http_status == 403:
        signals.append(f"http_status_{http_status}")

    path = url.split("?", 1)[0].casefold()
    if any(hint in path for hint in _URL_HINTS):
        signals.append("login_url_hint")

    for marker in _LOGIN_FORM_SIGNALS:
        if re.search(marker, html, re.IGNORECASE):
            signals.append("login_form_present")
            break

    # A password field plus a password-reset disclaimer is a recoverable state,
    # not a hard wall; don't treat those as authentication-required.
    if any(word in low for word in _DECLARATIVE_EXCLUDE) and not re.search(
        r">\s*sign in\s*<|>\s*log in\s*<", html, re.IGNORECASE
    ):
        signals = [s for s in signals if s != "login_form_present"]

    required = bool(signals)
    detail = ""
    if required:
        detail = (
            "Authentication required: the application page requires signing in. "
            "Paused for human login; no automatic submission was or will be attempted."
        )
    return AuthRequirement(
        url=url, required=required, signals=tuple(dict.fromkeys(signals)), detail=detail
    )


def auth_from_markers(url: str, markers: dict[str, Any]) -> AuthRequirement:
    """Convenience API over detect_auth_required for drivers that pass markers."""
    return detect_auth_required(
        url=url,
        text=markers.get("text", ""),
        html=markers.get("html", ""),
        title=markers.get("title", ""),
        http_status=markers.get("http_status"),
    )
