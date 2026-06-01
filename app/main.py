"""
main.py
-------
FastAPI application entry point for Maverick.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="Maverick",
    description="AI-powered personal assistant for care coordination.",
    version="0.1.0",
)

# Allow the frontend (any origin during development) to talk to the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "Maverick", "docs": "/docs"}
