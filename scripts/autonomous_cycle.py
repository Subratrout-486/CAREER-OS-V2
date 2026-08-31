#!/usr/bin/env python3
"""Run the live Career OS workers as one bounded, resumable cycle.

The workers remain independently testable. This controller simply gives them a
shared execution loop: discover -> process -> finalize -> verify. A later pass
is useful when the previous pass exposes newly eligible work. Failures are
recorded without echoing environment secrets.
"""
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
    ("discovery", "scripts/public_job_api_worker.py"),
    ("processing", "scripts/notion_job_worker_runtime.py"),
    ("finalization", "scripts/notion_resume_finalize.py"),
    ("smoke", "scripts/native_job_smoke_test.py"),
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
    # Keep CI logs bounded. Detailed artifacts belong in .career-os reports.
    output = proc.stdout[-4000:] if proc.stdout else ""
    return {"step": name, "script": script, "exit_code": proc.returncode, "tail": output}


def main() -> int:
    passes = max(1, min(int(os.getenv("CAREER_OS_CYCLE_PASSES", "2")), 4))
    results: list[dict[str, object]] = []
    overall_success = True

    for cycle in range(1, passes + 1):
        cycle_results: list[dict[str, object]] = []
        for name, script in STEPS:
            result = run_step(name, script)
            result["pass"] = cycle
            cycle_results.append(result)
            if result["exit_code"] != 0:
                overall_success = False
                # A systemic processing failure should stop; diagnostic smoke
                # failure must not erase successful intake/finalization work.
                if name == "processing":
                    break
        results.extend(cycle_results)
        if any(r["exit_code"] != 0 and r["step"] == "processing" for r in cycle_results):
            break

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "passes_requested": passes,
        "success": overall_success,
        "steps": results,
    }
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": overall_success, "passes": passes, "steps": len(results)}))
    return 0 if overall_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
