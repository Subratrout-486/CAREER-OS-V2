from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass(frozen=True)
class FormField:
    key: str
    label: str
    input_type: str = "text"
    required: bool = False
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class FieldMapping:
    field: FormField
    profile_key: str | None
    value: str | None
    confidence: float


@dataclass
class ApplicationForm:
    url: str
    fields: list[FormField] = field(default_factory=list)
    mappings: list[FieldMapping] = field(default_factory=list)


ALIASES: dict[str, tuple[str, ...]] = {
    "first_name": ("first name", "given name", "forename"),
    "last_name": ("last name", "surname", "family name"),
    "full_name": ("full name", "name"),
    "email": ("email", "e-mail", "email address"),
    "phone": ("phone", "mobile", "telephone", "phone number"),
    "location": ("location", "city", "current location", "address"),
    "linkedin_url": ("linkedin", "linkedin url", "linkedin profile"),
    "portfolio_url": ("portfolio", "personal website", "website"),
    "github_url": ("github", "github url", "github profile"),
    "work_authorization": ("work authorization", "authorized to work", "legally authorized"),
    "sponsorship": ("sponsorship", "visa sponsorship", "require sponsorship"),
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def map_profile_fields(fields: list[FormField], profile: dict[str, Any]) -> list[FieldMapping]:
    """Deterministically map known fields; unknown questions stay unmapped."""
    exact = {_norm(str(k)): (str(k), str(v)) for k, v in profile.items() if v not in (None, "")}
    result: list[FieldMapping] = []
    for field in fields:
        label = _norm(field.label)
        best_key: str | None = None
        best_value: str | None = None
        best_score = 0.0
        for key, aliases in ALIASES.items():
            for candidate in (key, *aliases):
                candidate_norm = _norm(candidate)
                score = 1.0 if label == candidate_norm else 0.85 if candidate_norm in label else 0.0
                if score > best_score and key in profile and profile[key] not in (None, ""):
                    best_key, best_value, best_score = key, str(profile[key]), score
        if best_score == 0.0 and label in exact:
            best_key, best_value, best_score = exact[label][0], exact[label][1], 1.0
        result.append(FieldMapping(field, best_key, best_value, best_score))
    return result


class BrowserApplicationRunner:
    """Inspect and fill forms with Playwright, never submit them."""

    async def inspect(self, url: str) -> ApplicationForm:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            raw = await page.locator("input, textarea, select").evaluate_all(
                """els => els.map((el, i) => ({
                    key: el.name || el.id || `field-${i}`,
                    label: el.labels?.[0]?.innerText || el.getAttribute('aria-label') || el.name || el.id || '',
                    input_type: el.tagName.toLowerCase() === 'select' ? 'select' : (el.type || 'text'),
                    required: !!el.required,
                    options: el.tagName.toLowerCase() === 'select' ? Array.from(el.options).map(o => o.textContent?.trim() || '') : []
                }))"""
            )
            await browser.close()
        return ApplicationForm(url=url, fields=[FormField(**item) for item in raw])

    async def fill(self, url: str, mappings: list[FieldMapping]) -> dict[str, Any]:
        from playwright.async_api import async_playwright

        filled: list[str] = []
        skipped: list[str] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            for mapping in mappings:
                if not mapping.profile_key or mapping.value is None or mapping.confidence < 0.85:
                    skipped.append(mapping.field.key)
                    continue
                locator = page.locator(f"#{mapping.field.key}, [name='{mapping.field.key}']").first
                if await locator.count() == 0:
                    skipped.append(mapping.field.key)
                    continue
                try:
                    if mapping.field.input_type == "select":
                        await locator.select_option(label=mapping.value)
                    elif mapping.field.input_type in {"checkbox", "radio"}:
                        if mapping.value.casefold() in {"true", "yes", "1"}:
                            await locator.check()
                    else:
                        await locator.fill(mapping.value)
                    filled.append(mapping.field.key)
                except Exception:
                    skipped.append(mapping.field.key)
            await browser.close()
        return {"url": url, "filled": filled, "skipped": skipped, "submitted": False}
