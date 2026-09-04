"""Standalone HTTP application for the ARACHNE Career OS control plane.

Serves the live ARACHNE web application (dashboard/index.html) and mounts the
control-plane API. All views read real persisted state; there is no hardcoded
demo data.
"""

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


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    if _DASHBOARD.exists():
        return FileResponse(str(_DASHBOARD))
    return HTMLResponse("<h1>ARACHNE</h1><p>dashboard/index.html not found</p>")
