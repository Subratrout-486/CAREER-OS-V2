from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts" / "notion_application_worker.py"


def test_application_worker_direct_execution_resolves_scripts_package():
    env = os.environ.copy()
    env.pop("NOTION_TOKEN", None)
    result = subprocess.run(
        [sys.executable, str(WORKER)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "NOTION_TOKEN is not configured" in result.stderr
    assert "ModuleNotFoundError: No module named 'scripts'" not in result.stderr
    assert "ModuleNotFoundError: No module named 'career_os'" not in result.stderr
