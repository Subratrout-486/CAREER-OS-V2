#!/usr/bin/env python3
"""Run the live Career OS workers as one bounded, resumable cycle."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".career-os" / "autonomous-cycle-report.json"
STEPS = (
    ("discovery", "scripts/public_job_api_worker.py", True),
    ("processing", "scripts/notion_job_worker_runtime.py", True),
    ("finalization", "scripts/notion_resume_finalize.py", True),
    ("smoke", "scripts/native_job_smoke_test.py", True),
)


def run_step(name: str, script: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {"step": name, "script": script, "exit_code": proc.returncode,
            "tail": (proc.stdout or "")[-4000:]}


def main() -> int:
    passes = max(1, min(int(os.getenv("CAREER_OS_CYCLE_PASSES", "2")), 4))
    results: list[dict[str, object]] = []
    systemic_failure = False

    for cycle in range(1, passes + 1):
        cycle_results: list[dict[str, object]] = []
        for name, script, systemic in STEPS:
            result = run_step(name, script)
            result["pass"] = cycle
            cycle_results.append(result)
            if result["exit_code"] != 0 and systemic:
                systemic_failure = True
                break
        results.extend(cycle_results)
        if any(r["exit_code"] != 0 for r in cycle_results):
            break

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "passes_requested": passes,
        "success": not systemic_failure,
        "steps": results,
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": not systemic_failure, "passes": passes, "steps": len(results)}))
    return 1 if systemic_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
