#!/usr/bin/env python3
"""Runtime adapter for the live Career OS Notion Jobs schema.

The connected Jobs data source exposes `Status` as a Notion `select` property,
not the newer `status` property type. Keep the core worker unchanged and adapt
its page-update payload at the integration boundary so the automation matches
the actual connected schema.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / "scripts" / "notion_job_worker.py"
spec = importlib.util.spec_from_file_location("career_os_notion_job_worker", WORKER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {WORKER_PATH}")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def update_page(page_id: str, updates: dict[str, Any]) -> None:
    """Write values using the live Jobs data-source property types."""
    properties: dict[str, Any] = {}
    select_properties = {
        "Status",
        "Processing Stage",
        "Resume Status",
        "Fit Decision",
        "Role Family",
    }
    for name, value in updates.items():
        if name in select_properties:
            properties[name] = {"select": {"name": value}} if value else {"select": None}
        elif name == "Fit Score":
            properties[name] = {"number": float(value) if value is not None else None}
        elif name in {"Job URL", "Application URL", "Resume URL"}:
            properties[name] = {"url": value or None}
        else:
            properties[name] = (
                {"rich_text": [{"type": "text", "text": {"content": str(value)[:1900]}}]}
                if value
                else {"rich_text": []}
            )
    worker.notion_request("PATCH", f"/pages/{page_id}", {"properties": properties})


worker.update_page = update_page


if __name__ == "__main__":
    raise SystemExit(worker.main())
