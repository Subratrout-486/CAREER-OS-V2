"""Notion-backed Resume Library integration for Career OS."""
from __future__ import annotations

import os
from typing import Any

DEFAULT_RESUME_LIBRARY_DATA_SOURCE_ID = "71806dff-39bf-4d1c-b3fd-022504d26c72"
NOTION_VERSION = os.environ.get("NOTION_VERSION", "2026-03-11")


def normalize(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def rich_text(value: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": str(value)[:1900]}}]} if value else {"rich_text": []}


def title(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": str(value)[:1900]}}]}


def build_resume_library_properties(
    *,
    resume_name: str,
    status: str,
    role_family: str,
    version: str,
    source: str,
    claims_verified: bool,
    notes: str = "",
    ats_score: float | None = None,
    job_id: str | None = None,
    file_upload_id: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Build a Notion Resume Library page-property payload."""
    if status not in {"Canonical", "Tailored", "Draft", "Archived"}:
        raise ValueError(f"Unsupported resume status: {status}")
    properties: dict[str, Any] = {
        "Resume": title(resume_name),
        "Status": {"select": {"name": status}},
        "Role Family": rich_text(role_family),
        "Version": rich_text(version),
        "Source": rich_text(source),
        "Claims Verified": {"checkbox": bool(claims_verified)},
        "Notes": rich_text(notes),
    }
    if ats_score is not None:
        properties["ATS Score"] = {"number": float(ats_score)}
    if job_id:
        properties["Job"] = {"relation": [{"id": job_id}]}
    if file_upload_id:
        file_obj: dict[str, Any] = {"type": "file_upload", "file_upload": {"id": file_upload_id}}
        if filename:
            file_obj["name"] = filename
        properties["File"] = {"files": [file_obj]}
    return properties


def next_version(existing_versions: list[str], prefix: str = "v") -> str:
    """Return the next integer version from values such as v1, v2, v3."""
    highest = 0
    for value in existing_versions:
        normalized = normalize(value)
        if normalized.startswith(prefix.casefold()):
            suffix = normalized[len(prefix):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        elif normalized.isdigit():
            highest = max(highest, int(normalized))
    return f"{prefix}{highest + 1}"


def library_properties_from_page(page: dict[str, Any], page_property: str = "Job") -> dict[str, Any]:
    """Extract a compact indexable record from an existing Resume Library page."""
    props = page.get("properties", {}) or {}
    return {"properties": props, "page_id": page.get("id"), "relation_property": page_property}
