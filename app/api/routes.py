"""
routes.py
---------
FastAPI router for all Maverick endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.graph.workflow import run_workflow
from app.memory.memory_store import MemoryStore
from app.audit.audit_log import AuditLog

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    response: str
    agents_used: list[str]
    details: dict


class ContextUpdateRequest(BaseModel):
    key: str
    value: str


class AppointmentRequest(BaseModel):
    doctor: str
    date: str
    notes: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse, summary="Send a request to Maverick")
async def handle_query(body: QueryRequest) -> QueryResponse:
    """
    Main endpoint — routes Patrick's request through the full agent workflow
    and returns a synthesised response.
    """
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    result = run_workflow(body.query)
    return QueryResponse(**result)


@router.get("/context", summary="Retrieve all stored patient context")
async def get_context() -> dict[str, str]:
    """Return the full patient context dictionary."""
    return MemoryStore().get_all_context()


@router.post("/context", summary="Set or update a context value")
async def set_context(body: ContextUpdateRequest) -> dict[str, str]:
    """Insert or update a single context key/value pair."""
    store = MemoryStore()
    store.set_context(body.key, body.value)
    return {"key": body.key, "value": body.value}


@router.get("/appointments/{doctor}", summary="Get appointment history for a doctor")
async def get_appointments(doctor: str) -> list[dict]:
    """Return all appointments for the given doctor, newest first."""
    return MemoryStore().get_appointments(doctor)


@router.post("/appointments", summary="Manually log an appointment")
async def add_appointment(body: AppointmentRequest) -> dict:
    """Directly add an appointment record without going through the workflow."""
    MemoryStore().add_appointment(body.doctor, body.date, body.notes)
    return {"status": "created", "doctor": body.doctor, "date": body.date}


@router.get("/audit/logs", summary="Get all audit log entries")
async def get_audit_logs() -> list[dict]:
    """Return every audit log entry, newest first."""
    return AuditLog().get_logs()


@router.get("/audit/logs/{agent_name}", summary="Get audit logs for a specific agent")
async def get_audit_logs_for_agent(agent_name: str) -> list[dict]:
    """Return audit log entries filtered by agent name."""
    return AuditLog().get_logs_for_agent(agent_name)


@router.get("/health", summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "Maverick"}
