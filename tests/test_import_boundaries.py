import os
import subprocess
import sys


def test_career_os_root_import_does_not_eagerly_load_pipeline():
    code = "import career_os; import career_os.autonomy.provider_controller; print('ok')"
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True, env=env)
    assert result.stdout.strip() == "ok"
