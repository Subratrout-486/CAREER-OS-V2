"""Dynamic application-form inspection and verified field mapping.

The engine cannot assume a prepared plan already contains a populated
``fields`` mapping. This module safely inspects an application form from a
browser snapshot (HTML text) or a live Playwright page and produces a
deterministic list of :class:`FormField` descriptors.

Field discovery uses only observable attribute signal:

* ``id`` / ``name``
* associated ``<label>`` text
* ``aria-label``
* ``placeholder``
* input ``type``
* ``<select>`` options
* textarea / file inputs

Mapping then resolves each described field against the *verified candidate
Source of Truth* profile using explicit alias rules. A required field with no
verified value is never invented and never filled with a guess; it is reported
as a review requirement. Optional unknown fields are dropped.

The mapping is deliberately deterministic and explicit: no model, no AI and no
guessing is involved in producing candidate values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

_SKIP_INPUT_TYPES = {
    "hidden",
    "submit",
    "button",
    "reset",
    "image",
    "password",
}

_FORM_CONTROL = re.compile(r"((?:<input\b[^>]*>|<select\b[^>]*>|<textarea\b[^>]*>))", re.IGNORECASE)
_SELECT_OPTION = re.compile(r"<option\b[^>]*>(.*?)</option>", re.IGNORECASE | re.DOTALL)
_PLACEHOLDER_OPTIONS = {
    "",
    "--",
    "please select",
    "select",
    "select one",
    "select an option",
    "choose",
    "choose one",
    "not specified",
    "none",
}


def _attr(html: str, name: str) -> str | None:
    """Best-effort extraction of a single HTML attribute value."""
    match = re.search(
        rf"\b{re.escape(name)}\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))",
        html,
        re.IGNORECASE,
    )
    if not match:
        return None
    return (match.group(1) or match.group(2) or match.group(3) or "").strip()


def _text_content(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).replace("&nbsp;", " ")


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


@dataclass(frozen=True)
class FormField:
    """A discovered application form control."""

    key: str
    input_type: str
    label: str = ""
    name: str | None = None
    field_id: str | None = None
    placeholder: str = ""
    aria_label: str = ""
    required: bool = False
    options: tuple[str, ...] = field(default_factory=tuple)
    value_hint: str | None = None

    @property
    def all_labels(self) -> str:
        return " ".join(part for part in (self.label, self.placeholder, self.aria_label, self.value_hint or "") if part)


def _label_for(html: str, tag: str, control_id: str) -> str:
    """Associate a label with a control: explicit ``for``, ``aria-labelledby``, or closest preceding label."""
    if control_id:
        for_label = re.search(
            rf"<label\b[^>]*\bfor\s*=\s*[\"']{re.escape(control_id)}[\"'][^>]*>(.*?)</label>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if for_label:
            return _clean_text(_text_content(for_label.group(1)))
        labelled_by = _attr(tag, "aria-labelledby")
        if labelled_by:
            by_label = re.search(
                rf"<label\b[^>]*\bid\s*=\s*[\"']{re.escape(labelled_by.strip())}[\"'][^>]*>(.*?)</label>",
                html,
                re.IGNORECASE | re.DOTALL,
            )
            if by_label:
                return _clean_text(_text_content(by_label.group(1)))
    snippet = html[: html.find(tag)]
    labels = list(re.finditer(r"<label\b[^>]*>(.*?)</label>", snippet, re.IGNORECASE | re.DOTALL))
    if labels:
        # Only use the closest preceding label when no other form control sits
        # between it and this control; otherwise the association is ambiguous.
        gap = snippet[labels[-1].end():]
        if not _FORM_CONTROL.search(gap):
            return _clean_text(_text_content(labels[-1].group(1)))
    return ""


def discover_fields(html: str) -> list[FormField]:
    """Discover form controls from raw HTML without a live DOM.

    Works on the snapshot the engine already keeps in ``page_html`` so field
    discovery does not require an extra browser round-trip. ``input`` types that
    cannot be filled by automation (hidden, password, buttons) are skipped.
    """
    fields: list[FormField] = []
    appended_keys: set[str] = set()

    def add(field: FormField) -> None:
        if field.key and field.key not in appended_keys:
            appended_keys.add(field.key)
            fields.append(field)

    for match in _FORM_CONTROL.finditer(html):
        tag = match.group(0)
        end = match.end()
        tag_name = re.match(r"<([a-z]+)", tag, re.IGNORECASE).group(1).casefold()  # type: ignore[union-attr]
        control_id = _attr(tag, "id") or ""
        name = _attr(tag, "name") or ""
        key = name or control_id or f"{tag_name}-field-{len(fields) + 1}"
        input_type = (_attr(tag, "type") or ("select" if tag_name == "select" else "text")).casefold()

        if tag_name not in {"select", "textarea"} and input_type in _SKIP_INPUT_TYPES:
            continue
        if input_type == "file":
            is_required = bool("required" in tag)
            add(
                FormField(
                    key=key,
                    input_type="file",
                    label=_label_for(html, tag, control_id),
                    name=name or None,
                    field_id=control_id or None,
                    placeholder=_clean_text(_attr(tag, "placeholder") or ""),
                    aria_label=_clean_text(_attr(tag, "aria-label") or ""),
                    required=is_required,
                    value_hint="resume",
                )
            )
            continue

        label = _label_for(html, tag, control_id)
        required = bool("required" in tag or (_attr(tag, "aria-required") or "").casefold() in {"true", "1"})

        if tag_name == "select":
            close = html.find("</select>", end)
            select_body = html[end:close] if close != -1 else ""
            option_values = [
                _clean_text(_text_content(opt)) for opt in _SELECT_OPTION.findall(select_body)
            ]
            options = tuple(dict.fromkeys(v for v in option_values if _norm(v) not in _PLACEHOLDER_OPTIONS))
            add(
                FormField(
                    key=key,
                    input_type="select",
                    label=label,
                    name=name or None,
                    field_id=control_id or None,
                    placeholder=_clean_text(_attr(tag, "placeholder") or ""),
                    aria_label=_clean_text(_attr(tag, "aria-label") or ""),
                    required=required,
                    options=options,
                )
            )
        elif tag_name == "textarea":
            add(
                FormField(
                    key=key,
                    input_type="textarea",
                    label=label,
                    name=name or None,
                    field_id=control_id or None,
                    placeholder=_clean_text(_attr(tag, "placeholder") or ""),
                    aria_label=_clean_text(_attr(tag, "aria-label") or ""),
                    required=required,
                )
            )
        else:
            add(
                FormField(
                    key=key,
                    input_type=input_type,
                    label=label,
                    name=name or None,
                    field_id=control_id or None,
                    placeholder=_clean_text(_attr(tag, "placeholder") or ""),
                    aria_label=_clean_text(_attr(tag, "aria-label") or ""),
                    required=required,
                )
            )
    return fields


# ---------------------------------------------------------------------------
# Verified candidate-value mapping
# ---------------------------------------------------------------------------

# concept -> [label aliases] ; each alias is matched as a normalized substring
# of the joined label/placeholder/aria-label text. The value is read exclusively
# from the candidate Source of Truth (never invented).
_ALIASES: dict[str, tuple[str, ...]] = {
    "first_name": ("first name", "given name", "forename"),
    "last_name": ("last name", "surname", "family name"),
    "full_name": ("full name", "candidate name", "your name", "name"),
    "email": ("email", "e-mail", "email address"),
    "phone": ("phone", "mobile", "telephone", "phone number", "contact number"),
    "location": ("location", "city", "current location", "address", "based"),
    "linkedin_url": ("linkedin", "linkedin profile", "linkedin url"),
    "portfolio_url": ("portfolio", "personal website", "website", "github url", "github"),
    "work_authorization": ("authorization", "authorized", "work authorization", "legally authorized", "right to work"),
    "sponsorship": ("sponsorship", "visa sponsorship", "require sponsorship", "now or in the future"),
    "notice_period": ("notice period", "availability", "how soon can you start", "start date"),
    "current_employer": ("current employer", "current company"),
    "desired_salary": ("salary", "compensation expectation", "expected salary", "desired salary"),
    "education": ("education", "degree", "qualification", "college", "university"),
    "experience_years": ("years of experience", "years experience", "total experience"),
    "gender": ("gender",),
    "dob": ("date of birth", "dob"),
    "highest_education": ("highest education", "highest degree", "education level"),
    "resume": ("resume", "cv", "curriculum vitae", "attach resume", "upload resume", "attach cv", "upload cv"),
    "linkedin_required": ("linkedin profile url",),
}

_OPTIONAL_CONCEPTS = {
    "linkedin_url",
    "portfolio_url",
    "github_url",
    "desired_salary",
    "gender",
    "dob",
    "highest_education",
    "current_employer",
    "notice_period",
}


@dataclass(frozen=True)
class FieldMapping:
    """Resolved mapping of one discovered field to a verified candidate value."""

    field: FormField
    concept: str | None
    value: str | None
    resolved: bool
    optional: bool = False
    review: bool = False
    reason: str = ""


def _candidate_value(concept: str, profile: Mapping[str, Any]) -> str | None:
    value = profile.get(concept)
    if value is None:
        value = (profile.get("candidate") or {}).get(concept) if isinstance(profile.get("candidate"), Mapping) else None
    if value is None and concept == "full_name":
        cand = profile.get("candidate") or {}
        first = cand.get("first_name") if isinstance(cand, Mapping) else profile.get("first_name")
        last = cand.get("last_name") if isinstance(cand, Mapping) else profile.get("last_name")
        if first and last:
            return f"{first} {last}"
    if concept == "work_authorization":
        return _work_authorization_value(profile)
    if concept == "sponsorship":
        return _sponsorship_value(profile)
    if concept == "education":
        return _education_value(profile)
    if concept == "experience_years":
        return _experience_years_value(profile)
    if isinstance(value, (bool, int, float)):
        return str(value)
    return str(value).strip() if value not in (None, "") else None


def _work_authorization_value(profile: Mapping[str, Any]) -> str | None:
    cand = profile.get("candidate") or {}
    value = cand.get("work_authorization") or cand.get("work_authorization_status")
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    raw = str(value).casefold()
    if raw in {"yes", "true", "authorized", "legally authorized", "authorized to work"}:
        return "Yes"
    if raw in {"no", "false", "not authorized", "not authorized to work"}:
        return "No"
    return str(value)


def _sponsorship_value(profile: Mapping[str, Any]) -> str | None:
    cand = profile.get("candidate") or {}
    value = cand.get("sponsorship") or cand.get("visa_sponsorship")
    if value in (None, ""):
        return None
    raw = str(value).casefold()
    if raw in {"no", "false", "none", "not required", "do not require"}:
        return "No"
    if raw in {"yes", "true", "required", "yes, i require sponsorship"}:
        return "Yes"
    return str(value)


def _education_value(profile: Mapping[str, Any]) -> str | None:
    education = profile.get("education") if isinstance(profile, Mapping) else None
    if isinstance(education, list) and education:
        first = education[0]
        if isinstance(first, Mapping):
            qualification = str(first.get("qualification", "")).strip()
            institution = str(first.get("institution", "")).strip()
            if qualification:
                return f"{qualification}, {institution}" if institution else qualification
    return None


def _experience_years_value(profile: Mapping[str, Any]) -> str | None:
    cand = profile.get("candidate") or {}
    value = cand.get("years_of_experience") or cand.get("experience_years")
    if value in (None, ""):
        return None
    raw = str(value).casefold()
    # Only a numeric answer may be filled; textual experience descriptions are
    # never used to answer a "years of experience" question because they are not
    # a direct answer.
    numeric = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)?\s*$", raw)
    if numeric:
        return numeric.group(1)
    return None


def match_concept(text: str) -> tuple[str | None, float]:
    """Determine which candidate concept a joined label maps to."""
    normalized = _norm(text)
    best: str | None = None
    best_score = 0.0
    for concept, aliases in _ALIASES.items():
        for alias in aliases:
            alias_norm = _norm(alias)
            if alias_norm == normalized:
                return concept, 1.0
            if alias_norm and alias_norm in normalized:
                score = 0.9 if normalized.startswith(alias_norm) or normalized.endswith(alias_norm) else 0.85
                if score > best_score:
                    best, best_score = concept, score
    return best, best_score


def map_discovered_fields(
    fields: list[FormField], profile: Mapping[str, Any], *, threshold: float = 0.85
) -> list[FieldMapping]:
    """Map discovered fields to verified candidate values.

    Rules:

    * A concept is only resolved when a verified value exists in ``profile``.
    * Required fields with no verified value become ``review=True``.
    * Optional unknown fields are skipped (``resolved=False``, ``optional=True``).
    """
    mappings: list[FieldMapping] = []
    for field in fields:
        joined = field.all_labels or field.key
        concept, score = match_concept(joined)
        if concept is None:
            mappings.append(
                FieldMapping(
                    field=field,
                    concept=None,
                    value=None,
                    resolved=False,
                    optional=not field.required,
                    review=field.required,
                    reason="no matching verified candidate concept",
                )
            )
            continue
        value = _candidate_value(concept, profile)
        if value is None:
            optional = concept in _OPTIONAL_CONCEPTS or not field.required
            mappings.append(
                FieldMapping(
                    field=field,
                    concept=concept,
                    value=None,
                    resolved=False,
                    optional=optional,
                    review=field.required and concept not in _OPTIONAL_CONCEPTS,
                    reason=f"no verified {concept} in Source of Truth",
                )
            )
            continue
        mappings.append(
            FieldMapping(
                field=field,
                concept=concept,
                value=value,
                resolved=True,
                optional=concept in _OPTIONAL_CONCEPTS,
            )
        )
    return mappings


def fields_to_plan(fields: list[FormField]) -> list[dict[str, Any]]:
    return [
        {
            "key": f.key,
            "input_type": f.input_type,
            "label": f.label,
            "placeholder": f.placeholder,
            "aria_label": f.aria_label,
            "required": f.required,
            "options": list(f.options),
        }
        for f in fields
    ]