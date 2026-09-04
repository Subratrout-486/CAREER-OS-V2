"""Standalone HTTP application for direct Arachne integration."""
from fastapi import FastAPI

from career_os.arachne_api import create_arachne_router
from career_os.state_api import create_state_router

app = FastAPI(title="CareerOS V2 API")
app.include_router(create_arachne_router())
app.include_router(create_state_router())
