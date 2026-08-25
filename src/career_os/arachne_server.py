"""Deployable ASGI application for the Arachne frontend."""
from fastapi import FastAPI

from career_os.arachne_api import create_arachne_router

app = FastAPI(
    title="CareerOS V2 Arachne API",
    version="0.1.0",
    description="Direct review-only API boundary for the Arachne Career Intelligence OS UI.",
)
app.include_router(create_arachne_router())
