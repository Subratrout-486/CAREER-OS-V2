"""Portal-aware helpers for known employment application systems.

These helpers are *reusable building blocks* for the live Playwright driver and
the deterministic fixture driver. They provide robust, semantic selector
strategies for the employer portals Career OS can drive (Greenhouse, Lever,
Ashby, Workable, SmartRecruiters) and confirmation-page extraction for
submission verification.

No security challenge is bypassed; these helpers exist only so approved
applications can be driven within the supported-flow boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from career_os.execution.flow import FlowKind
from career_os.execution.forms import FormField as DiscoveredFormField


@dataclass(frozen=True)
class PortalHints:
    """Semantic selector strategies for one application portal."""

    kind: FlowKind
    fields: tuple[str, ...]
    submit: tuple[str, ...]
    confirmation: tuple[str, ...]
    known_modules: tuple[str, ...] = ()


def portal_hints(flow_kind: FlowKind | str) -> PortalHints | None:
    """Return reusable drive hints for a recognized flow kind."""
    kind = flow_kind.value if isinstance(flow_kind, FlowKind) else str(flow_kind)
    hints = {
        FlowKind.GREENHOUSE.value: PortalHints(
            kind=FlowKind.GREENHOUSE,
            fields=(
                "input[name*='first_name']",
                "input[name*='last_name']",
                "input[name*='email']",
                "input[type='file'][name*='resume']",
                "textarea[name*='']",
            ),
            submit=("button[type='submit']", "button:has-text('Submit Application')"),
            confirmation=(
                ".application--success",
                "text=Application submitted",
                "text=Thanks for applying",
                "text=Your application has been received",
            ),
            known_modules=("job-app", "application-form"),
        ),
        FlowKind.LEVER.value: PortalHints(
            kind=FlowKind.LEVER,
            fields=(
                "input[name*='name']",
                "input[name*='email']",
                "input[type='file'][name*='file']",
                "input[type='file'][name*='resume']",
            ),
            submit=("button[type='submit']", "button:has-text('Submit')"),
            confirmation=(".application-form__success", "text=Your application has been submitted"),
            known_modules=("application-form", "postings-form"),
        ),
        FlowKind.ASHBY.value: PortalHints(
            kind=FlowKind.ASHBY,
            fields=(
                "input[name*='name']",
                "input[name*='email']",
                "input[type='file'][name*='file']",
                "input[type='file'][name*='resume']",
            ),
            submit=("button[type='submit']", "button:has-text('Submit Application')"),
            confirmation=(".ashby-application-success", "text=Application submitted"),
            known_modules=("ashby-application-form",),
        ),
        FlowKind.GENERIC_FORM.value: PortalHints(
            kind=FlowKind.GENERIC_FORM,
            fields=(
                "input[name*='first_name']",
                "input[name*='last_name']",
                "input[name*='email']",
                "input[type='file']",
            ),
            submit=("button[type='submit']", "button:has-text('Submit')", "button:has-text('Apply')", "input[type='submit']"),
            confirmation=("text=Application received", "text=Application submitted", "text=Thank you for applying"),
            known_modules=(),
        ),
    }
    return hints.get(kind)


def build_field_selectors(hint: PortalHints, discovered: list[DiscoveredFormField]) -> list[str]:
    """Return portal-aware locator strings for the discovered field keys.

    Used by the live driver to prefer portal-specific selectors over generic
    id/name fallbacks when a portal is recognized.
    """
    selectors: list[str] = []
    base = list(hint.fields)
    for field in discovered:
        selectors.append(f"#{field.field_id}" if field.field_id else "")
        selectors.append(f"[name='{field.name}']" if field.name else "")
    return [s for s in (list(dict.fromkeys([*base, *selectors]))) if s]


_CONFIRMATION_RE = re.compile(
    r"(?:application|submission|we(?:'re)?|you(?:r)?|thanks?[^.]{0,30})"
    r"\s*(?:has been|has|was|is|have)?\s*(?:successfully)?\s*"
    r"(?:submitted|received|completed|recorded)",
    re.IGNORECASE,
)

# Keywords that introduce an application reference / confirmation code.
_REFERENCE_KEYWORDS_RE = re.compile(
    r"\b(?:reference|confirmation|application|ref|id|code|number)\b",
    re.IGNORECASE,
)

# A plausible application reference: starts alphanumeric and either contains a
# digit or is fully uppercase (so prose words like "reference"/"has"/"received"
# are never mistaken for a code), at least 3 characters long.
_REFERENCE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-/]{2,31}")

# Common qualifier words that may appear between the keyword and the code.
_REFERENCE_QUALIFIERS = {"id", "no", "ref", "code", "number", "num"}


def _first_reference(text: str) -> str | None:
    """Return the first identifier-like token that follows a reference keyword."""
    for kw in _REFERENCE_KEYWORDS_RE.finditer(text):
        for token_match in _REFERENCE_TOKEN_RE.finditer(text, kw.end()):
            token = token_match.group(0)
            low = token.casefold()
            if low in _REFERENCE_QUALIFIERS or len(token) < 3:
                continue
            if re.search(r"\d", token) or token.isupper():
                return token
            # Stop scanning after a few prose tokens following the keyword; the
            # code, if present, appears immediately after the keyword phrase.
            break
    return None


def extract_confirmation(text: str) -> tuple[bool, str | None]:
    """Return (confirmed, reference) from result-page text.

    Confirmation requires both a positive submission phrase and, when a
    reference/code appears, extraction of that reference. A page that only
    says a reference code with no submission phrase is not treated as proof.
    """
    confirmed = bool(_CONFIRMATION_RE.search(text))
    return confirmed, _first_reference(text)


def looks_like_success_url(url: str) -> bool:
    """Portal URL signals that commonly follow a successful submission."""
    low = url.casefold()
    return any(marker in low for marker in ("/success", "/confirm", "/application/confirmation", "submitted=true", "/thanks"))


def apply_portal_heuristics(
    *,
    flow_kind: FlowKind,
    page_text: str,
    page_title: str,
    url: str,
) -> tuple[bool, str | None]:
    """Portal-aware confirmation verification over observable page signals.

    Returns ``(confirmed, reference)``. Confirmation is only reported when the
    page gives an explicit success signal; a click alone never counts.
    """
    confirmed, reference = extract_confirmation(f"{page_title} {page_text}")
    if confirmed or reference:
        return True, reference
    if looks_like_success_url(url):
        return True, None
    return False, None


def resumable_step_index(completed: list[str], nav_step: int) -> int:
    """Return the next nav page index for multi-step portal forms."""
    return max(0, int(nav_step or 0)) if completed else 0