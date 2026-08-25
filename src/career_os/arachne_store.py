"""Small file-backed index for Arachne's read API.

CareerOS checkpoints remain authoritative. This index only maps a canonical job
key to its latest completed checkpoint so the UI can discover processed jobs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArachneResultStore:
    def __init__(self, root: str | Path = ".career_os/arachne") -> None:
        self.root = Path(root)
        self.index_path = self.root / "index.json"

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.index_path)

    def record(self, job_key: str, trace_id: str, result: dict[str, Any]) -> None:
        data = self._read()
        data[job_key] = {"trace_id": trace_id, "result": result}
        self._write(data)

    def list(self) -> list[dict[str, Any]]:
        return [entry["result"] | {"trace_id": entry["trace_id"]} for entry in self._read().values()]

    def get(self, job_key: str) -> dict[str, Any] | None:
        entry = self._read().get(job_key)
        if not entry:
            return None
        return entry["result"] | {"trace_id": entry["trace_id"]}
