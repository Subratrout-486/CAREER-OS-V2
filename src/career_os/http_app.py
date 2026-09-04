"""Standalone HTTP application for the ARACHNE Career OS control plane.

Serves the live ARACHNE web application (dashboard/index.html) and mounts the
control-plane API. All views read real persisted state; there is no hardcoded
demo data.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

from career_os.arachne_api import create_arachne_router
from career_os.arachne_control import create_arachne_control_router
from career_os.state_api import create_state_router

_DASHBOARD = Path(__file__).resolve().parent.parent.parent / "dashboard" / "index.html"

app = FastAPI(
    title="ARACHNE · Career OS Control Plane",
    description="Live web control plane for the Career OS application automation platform.",
    version="0.1.0",
)
app.include_router(create_arachne_router())
app.include_router(create_arachne_control_router())
app.include_router(create_state_router())


def _state_roots() -> list[Path]:
    """Resolve the on-disk state roots the control plane persists to.

    Used by the readiness probe so a host can verify persistent storage is
    mounted and writable, not just that the process is up.
    """
    return [
        Path(os.getenv("CAREER_OS_EXECUTION_ROOT", ".career_os/executions")),
        Path(os.getenv("CAREER_OS_ARACHNE_ROOT", ".career_os/arachne")),
    ]


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Token-free liveness/readiness probe for hosts and load balancers.

    The dashboard and control-plane API are intentionally tokenless, so a
    public deployment needs a probe that does not require a bearer token.
    Verifies the persistent state roots exist and are writable (readiness),
    falling back to a degraded report if a mount is missing or read-only.
    """
    problems: list[str] = []
    roots = _state_roots()
    for root in roots:
        try:
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".healthz-write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            problems.append(f"{root}: {exc}")
    if problems:
        return {
            "status": "degraded",
            "service": "career-os-v2",
            "ready": False,
            "problems": problems,
        }
    return {"status": "ok", "service": "career-os-v2", "ready": True}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    if _DASHBOARD.exists():
        return FileResponse(str(_DASHBOARD))
    return HTMLResponse("<h1>ARACHNE</h1><p>dashboard/index.html not found</p>")
