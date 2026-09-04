"""Security-challenge detection for the application engine.

This module ONLY detects and classifies CAPTCHA / bot-detection / equivalent
security challenges. It deliberately contains no logic to solve, bypass, evade
or circumvent any of them - such techniques are out of scope for this project
and would be unethical and harmful (automated submission that deceives
employers' protections).

When a challenge is detected the caller must classify the application as
BLOCKED_SECURITY_CHALLENGE and stop, never reporting a false success.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_SIGNAL_PATTERNS = (
    re.compile(r"captcha", re.IGNORECASE),
    re.compile(r"\brecaptcha\b", re.IGNORECASE),
    re.compile(r"hcaptcha", re.IGNORECASE),
    re.compile(r"cloudflare", re.IGNORECASE),
    re.compile(r"turnstile", re.IGNORECASE),
    re.compile(r"challenge-platform", re.IGNORECASE),
    re.compile(r"g-recaptcha", re.IGNORECASE),
    re.compile(r"are you a robot", re.IGNORECASE),
    re.compile(r"verify you are human", re.IGNORECASE),
    re.compile(r"security check", re.IGNORECASE),
    re.compile(r"accessdenied", re.IGNORECASE),
    re.compile(r"cf-challenge", re.IGNORECASE),
    re.compile(r"geetest", re.IGNORECASE),
    re.compile(r"arkose", re.IGNORECASE),
    re.compile(r"funcaptcha", re.IGNORECASE),
    re.compile(r"protected by perimeterx", re.IGNORECASE),
)

_FRAME_IFRAME_SELECTORS = (
    "iframe[src*='captcha']",
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[src*='turnstile']",
    "iframe[src*='arkose']",
    "iframe[src*='funcaptcha']",
)

_CHALLENGE_SELECTORS = (
    "[class*='g-recaptcha']",
    "[class*='h-captcha']",
    "[id*='captcha']",
    "[class*='cf-turnstile']",
    "[class*='challenge']",
    "div[class*='wc-captcha']",
)


@dataclass(frozen=True)
class ChallengeDetection:
    """Result of scanning a page for a security challenge."""

    url: str
    blocked: bool
    kind: str | None = None
    signals: tuple[str, ...] = field(default_factory=tuple)
    detail: str = ""


def _scan_signals(url: str, text: str, html: str, selectors: dict[str, int]) -> tuple[list[str], str | None]:
    """Return matched body signals and a coarse kind label."""
    matched: list[str] = []
    haystack = f"{text} {html} {url}"
    for pattern in _SIGNAL_PATTERNS:
        if pattern.search(haystack):
            matched.append(pattern.pattern)
            break
    if selectors.get("captcha_selector"):
        matched.append("captcha_selector_present")
    if selectors.get("challenge_frame"):
        matched.append("challenge_iframe_present")

    if not matched:
        return [], None

    low = haystack.casefold()
    if any(word in low for word in ("recaptcha", "re-captcha", "g-recaptcha")):
        kind = "reCAPTCHA"
    elif any(word in low for word in ("hcaptcha", "h-captcha")):
        kind = "hCaptcha"
    elif any(word in low for word in ("turnstile", "cloudflare")):
        kind = "Cloudflare Turnstile"
    elif any(word in low for word in ("geetest", "arkose", "funcaptcha", "perimeterx")):
        kind = "vendor_captcha"
    elif "are you a robot" in low or "verify you are human" in low or "security check" in low:
        kind = "human_verification_page"
    else:
        kind = "captcha_equivalent"
    return matched, kind


def detect_challenge(
    *,
    url: str,
    text: str = "",
    html: str = "",
    title: str = "",
    iframe_count: int = 0,
    http_status: int | None = None,
) -> ChallengeDetection:
    """Detect and classify a security challenge from browser page signals.

    Callers pass whatever signals the driver can observe. The detector returns
    a structured result and never attempts to solve the challenge.
    """
    combined_text = f"{title} {text}"
    matches, kind = _scan_signals(url, combined_text, html, {"captcha_selector": 0, "challenge_frame": 0})

    for selector in _CHALLENGE_SELECTORS:
        if _pattern_in_html(html, selector):
            if "captcha_selector_present" not in matches:
                matches.append("captcha_selector_present")
            break
    for iframe_selector in _FRAME_IFRAME_SELECTORS:
        if iframe_selector.replace("iframe[src*=", "").replace("']", "") in html:
            if "challenge_iframe_present" not in matches:
                matches.append("challenge_iframe_present")
            break

    # re-derive kind after selector/iframe scan
    _, kind2 = _scan_signals(url, combined_text, html, {"captcha_selector": (1 if "captcha_selector_present" in matches else 0), "challenge_frame": (1 if "challenge_iframe_present" in matches else 0)})
    if kind2:
        kind = kind2

    blocked = bool(matches)
    detail = ""
    if blocked:
        detail = (
            f"Security challenge detected ({kind}). "
            "Application classified as BLOCKED_SECURITY_CHALLENGE; no automated bypass is attempted."
        )
    return ChallengeDetection(url=url, blocked=blocked, kind=kind, signals=tuple(dict.fromkeys(matches)), detail=detail)


def _pattern_in_html(html: str, selector: str) -> bool:
    # Best-effort DOM-ish selector presence check against raw HTML.
    tokens = re.findall(r"\[([^\]]+)\]", selector)[0] if "[" in selector and "]" in selector else ""
    if not tokens:
        return False
    attr, _, value = tokens.partition("*=")
    attr = attr.strip(" '")
    value = value.strip(" '")
    if value:
        return re.search(rf"{re.escape(attr)}=[\"']?[^\"'>]*{re.escape(value)}", html, re.IGNORECASE) is not None
    return False


def challenge_from_markers(
    url: str, markers: dict[str, Any]
) -> ChallengeDetection:
    """Convenience API over detect_challenge for drivers that pre-extract markers."""
    return detect_challenge(
        url=url,
        text=markers.get("text", ""),
        html=markers.get("html", ""),
        title=markers.get("title", ""),
        iframe_count=int(markers.get("iframe_count", 0)),
        http_status=markers.get("http_status"),
    )
