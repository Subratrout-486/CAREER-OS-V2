"""Standalone HTTP application for direct Arachne integration."""
from fastapi import FastAPI

from career_os.arachne_api import create_arachne_router

app = FastAPI(title="CareerOS V2 API")
app.include_router(create_arachne_router())
