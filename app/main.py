"""
main.py
-------
FastAPI application entry point for Maverick AI - Caregiver OS.

Start the server:
    uvicorn app.main:app --reload --port 8000
    OR
    python app/main.py

Interactive API docs:
    http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import agentscope
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router


# ---------------------------------------------------------------------------
# Lifespan: runs once at startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialises AgentScope once when the server starts so every request
    shares the same runtime without re-initialising on each call.

    AgentScope is used here purely as a pipeline / workflow orchestrator;
    the actual LLM calls are made directly via the Groq SDK inside each agent.
    We therefore pass a dummy model config so AgentScope is satisfied with its
    initialisation requirements.
    """
    agentscope.init(
        model_configs=[
            {
                "config_name": "dummy_groq",
                "model_type": "openai_chat",           # AgentScope built-in adapter
                "model_name": "llama3-70b-8192",       # ignored — we call Groq directly
                "api_key": "sk-placeholder",           # ignored — we call Groq directly
                "client_args": {
                    "base_url": "https://api.groq.com/openai/v1",
                },
                "generate_args": {
                    "temperature": 0.3,
                },
            }
        ],
        save_log=False,     # keep the working directory tidy during development
        save_code=False,
    )
    print("✅  AgentScope initialised — Maverick AI is ready.")
    yield                  # server runs while suspended here
    print("👋  Maverick AI shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Maverick AI - Caregiver OS",
    description=(
        "An AI-powered Care Coordination Assistant that helps caregivers "
        "manage medical needs, appointments, and logistics for their loved ones. "
        "Built with AgentScope (pipeline orchestration) and Groq (LLM inference)."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

# Allow any frontend origin during local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routes under /api  (e.g. POST /api/process-email)
app.include_router(router, prefix="/api")


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Quick sanity check — not included in the OpenAPI schema."""
    return {
        "service": "Maverick AI - Caregiver OS",
        "docs": "/docs",
        "health": "/api/health",
        "frontend": "/app",
    }


# Serve the frontend HTML at /app
_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@app.get("/app", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend UI."""
    return FileResponse(_FRONTEND_DIR / "index.html")


# Serve any other static assets (css, js, images) under /app/*
app.mount("/app", StaticFiles(directory=str(_FRONTEND_DIR)), name="frontend")


# ---------------------------------------------------------------------------
# Dev entrypoint: `python -m app.main` or `python app/main.py`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
