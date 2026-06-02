# 🧠 Maverick AI — Caregiver OS

> An AI-powered multi-agent care coordination assistant that helps caregivers manage medical appointments, logistics, and patient context for their loved ones.

Built with **AgentScope** (pipeline orchestration) · **Groq / LLaMA 3.1-8B Instant** (LLM inference) · **FastAPI** (REST API) · **SQLite** (persistent memory) · **Pydantic** (structured outputs)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Running the App](#running-the-app)
- [Using the Frontend Dashboard](#using-the-frontend-dashboard)
- [API Reference](#api-reference)
- [Testing the Pipeline (curl)](#testing-the-pipeline-curl)
- [Human-in-the-Loop (HITL) Approval Flow](#human-in-the-loop-hitl-approval-flow)
- [Data Persistence](#data-persistence)
- [Docker Deployment](#docker-deployment)
- [Troubleshooting](#troubleshooting)

---

## Overview

Maverick AI processes incoming caregiving emails through a **4-stage sequential agent pipeline**:

1. **Email Agent** — Parses & extracts structured data from the raw email
2. **Memory Agent** — Retrieves and synthesises relevant patient context from SQLite
3. **Logistics Agent** — Analyses scheduling conflicts, transport, and family notifications
4. **Council Agent** — Deliberates holistically and produces a final recommendation

The system supports a **Human-in-the-Loop (HITL) approval gate** that pauses the pipeline after the logistics stage for caregiver review before the council deliberation runs.

---

## Architecture

```
[Incoming Caregiving Email]
           │
           ▼
┌──────────────────────┐
│   Stage 1            │
│   Email Agent        │  ──► Extracts: event_type, doctor, times, urgency, transport_required
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Stage 2            │
│   Memory Agent       │  ──► Reads SQLite context: transport pref, doctor, family, schedule
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Stage 3            │
│   Logistics Agent    │  ──► Detects conflicts, transport rebooking, family notifications
└──────────┬───────────┘
           │
     [HITL Gate] ──────────► If require_approval=True: pause → return "awaiting_approval"
           │                  Caregiver reviews → POST /approve → resume
           ▼
┌──────────────────────┐
│   Stage 4            │
│   Council Agent      │  ──► Final recommendation, reasoning, tradeoffs, priority actions
└──────────────────────┘
           │
           ▼
     [Completed State]  ──► status="completed", all 4 agent outputs + SQLite audit log
```

All agents share a **state dictionary** threaded through [AgentScope](https://github.com/modelscope/agentscope) `SequentialPipeline` via `Msg.metadata`. Every call is validated by **Pydantic** and logged to SQLite.

---

## Project Structure

```
maverick-assignment/
├── app/
│   ├── agents/
│   │   ├── email_agent.py        # Stage 1 — email parser
│   │   ├── memory_agent.py       # Stage 2 — context retrieval
│   │   ├── logistics_agent.py    # Stage 3 — conflict & logistics analysis
│   │   └── council_agent.py      # Stage 4 — final deliberation
│   ├── graph/
│   │   └── workflow.py           # MaverickWorkflow: AgentScope SequentialPipeline + HITL
│   ├── api/
│   │   └── routes.py             # FastAPI router — all endpoints
│   ├── memory/
│   │   └── memory_store.py       # SQLite patient context & appointment history
│   ├── audit/
│   │   └── audit_log.py          # SQLite audit logging for every agent call
│   └── main.py                   # FastAPI app factory + AgentScope lifespan init
├── frontend/
│   └── index.html                # Single-file dark-themed dashboard (no framework)
├── data/
│   └── maverick.db               # SQLite database (auto-created on first run)
├── .env                          # Your secrets (not committed)
├── .env.example                  # Template for .env
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Production container
├── docker-compose.yml            # Multi-service compose
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM Inference** | [Groq](https://groq.com) — `llama-3.1-8b-instant` (500K tokens/day free tier) |
| **Pipeline Orchestration** | [AgentScope](https://github.com/modelscope/agentscope) v0.1.5 — `SequentialPipeline` |
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com) v0.111.0 |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org) v0.30.1 |
| **Data Validation** | [Pydantic](https://docs.pydantic.dev) v2.7+ |
| **Persistence** | SQLite (via Python `sqlite3` stdlib) |
| **Frontend** | Vanilla HTML/CSS/JS — zero framework, zero build step |
| **Env Config** | `python-dotenv` |

---

## Prerequisites

- **Python 3.11+** (tested on 3.12)
- **Groq API Key** — free at [console.groq.com](https://console.groq.com)
- **Git** (to clone the repository)

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/iampraneeth1116/Assignment.git
cd Assignment
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and add your Groq API key:

```env
GROQ_API_KEY=gsk_your_actual_key_here
```

> Get your free API key at [console.groq.com/keys](https://console.groq.com/keys)

---

## Running the App

### Start the backend server

```bash
# Make sure you're in the project root with venv active
uvicorn app.main:app --reload --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
✅  AgentScope initialised — Maverick AI is ready.
INFO:     Application startup complete.
```

> ⚠️ **If port 8000 is already in use**, free it first:
> ```bash
> kill $(lsof -t -i:8000) 2>/dev/null
> ```

### Verify the server is running

```bash
curl http://localhost:8000/api/health
# → {"status":"ok","service":"Maverick AI"}
```

Or visit: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### Interactive API docs (Swagger UI)

Open in your browser: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Using the Frontend Dashboard

The frontend is **served directly by the FastAPI backend** — open it via the backend URL, not as a local file.

```bash
# 1. Make sure the server is running:
uvicorn app.main:app --reload --port 8000

# 2. Then open in your browser:
open http://localhost:8000/app
```

> ⚠️ **Do NOT open `frontend/index.html` directly** (e.g. by double-clicking in Finder).  
> Opening as a `file://` URL blocks all API calls due to browser security (CORS policy).  
> Always use `http://localhost:8000/app`.

### Dashboard Tabs

The interface uses a **sidebar-tabbed layout** — click a tab to switch sections. No scrolling required.

| Tab | Icon | What it contains |
|---|---|---|
| **Process** | ⚙️ | Email textarea, Human Approval toggle, Process Email button, Pipeline progress bar |
| **Results** | 📊 | Expandable result cards for each of the 4 agents (auto-opens after completion) |
| **Audit Logs** | 📋 | Chronological table of every agent call — click Refresh to load |
| **Memory** | 🧠 | Patient context key-value grid from SQLite — click Load to display |

### Key UI Features

| Feature | What it does |
|---|---|
| **Header status dot** | Pulses green when API is online; turns red if server is unreachable |
| **Sidebar stage list** | Shows all 4 pipeline stages with live Pending / Running / Complete / Failed status |
| **Pipeline progress bar** | 4-step bar with animated blue pulse when running, green ✓ when complete |
| **HITL Approval Banner** | Appears on Process tab when `Require Human Approval` is checked — shows Approve and Reject buttons |
| **Auto tab switch** | Automatically switches to the Results tab when the pipeline completes |

---

## API Reference

### Phase 4 Endpoints

#### `POST /api/process-email`
Run the full 4-agent pipeline on a caregiving email.

**Request body:**
```json
{
  "email": "Hi Patrick, this is Dr. Patel's office...",
  "require_approval": false
}
```

**Response (status = completed):**
```json
{
  "email_analysis": { "event_type": "appointment_reschedule", "urgency": "medium", ... },
  "memory_context": { "doctor_known": true, "preferred_transport": "Medical Transport Service", ... },
  "logistics_analysis": { "conflict_detected": false, "action_items": [...], ... },
  "council_recommendation": { "recommendation": "...", "risk_level": "medium", "confidence_score": 0.8, ... },
  "status": "completed",
  "stages_completed": ["email_analysis complete", "memory_context complete", "logistics_analysis complete", "council_recommendation complete"]
}
```

**Response (status = awaiting_approval):** when `require_approval: true` — `council_recommendation` will be `{}` and `status` will be `"awaiting_approval"`.

---

#### `POST /api/approve`
Resume a pipeline that was paused at the HITL gate. Pass the full state dict returned from the previous `process-email` call.

**Request body:**
```json
{
  "raw_email": "...",
  "status": "awaiting_approval",
  "stages_completed": [...],
  "email_analysis": {...},
  "memory_context": {...},
  "logistics_analysis": {...},
  "council_recommendation": {}
}
```

**Response:** Same shape as `process-email`, with `status: "completed"` and `council_recommendation` populated.

---

#### `GET /api/audit-logs`
Retrieve all agent execution logs, newest first.

```bash
curl http://localhost:8000/api/audit-logs
```

---

#### `GET /api/audit-logs/{agent_name}`
Filter audit logs by agent. Valid agent names: `email_agent`, `memory_agent`, `logistics_agent`, `council_agent`, `workflow_orchestrator`.

```bash
curl http://localhost:8000/api/audit-logs/email_agent
```

---

#### `GET /api/memory`
Return the current patient context stored in SQLite.

```bash
curl http://localhost:8000/api/memory
```

---

#### `GET /api/health`
Liveness probe.

```bash
curl http://localhost:8000/api/health
# → {"status":"ok","service":"Maverick AI"}
```

---

### Legacy Endpoints (backwards-compatible)

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/query` | Send a natural-language query through the pipeline |
| `GET` | `/api/context` | Alias for `GET /api/memory` |
| `POST` | `/api/context` | Set a single context key/value |
| `GET` | `/api/appointments/{doctor}` | Get appointment history for a doctor |
| `POST` | `/api/appointments` | Manually log an appointment |
| `GET` | `/api/audit/logs` | Legacy audit log endpoint |

---

## Testing the Pipeline (curl)

### Quick health check
```bash
curl http://localhost:8000/api/health
```

### Full pipeline (no approval gate)
```bash
curl -X POST http://localhost:8000/api/process-email \
  -H "Content-Type: application/json" \
  -d '{
    "email": "Hi Patrick, this is Dr. Patel'\''s office. We need to reschedule your father'\''s appointment from Wednesday 2pm to Thursday 3pm. Please confirm if Medical Transport can also be rebooked.",
    "require_approval": false
  }'
```

### Pipeline with HITL approval gate
```bash
# Step 1 — submit email, pause before council
curl -X POST http://localhost:8000/api/process-email \
  -H "Content-Type: application/json" \
  -d '{"email": "Hi Patrick, appointment needs moving to Friday 11am.", "require_approval": true}'

# Step 2 — review the JSON response, then approve using the returned state
curl -X POST http://localhost:8000/api/approve \
  -H "Content-Type: application/json" \
  -d '<paste the full state JSON from step 1, with status="awaiting_approval">'
```

### Check patient memory
```bash
curl http://localhost:8000/api/memory
```

### View all audit logs
```bash
curl http://localhost:8000/api/audit-logs
```

### View logs for a specific agent
```bash
curl http://localhost:8000/api/audit-logs/council_agent
```

---

## Human-in-the-Loop (HITL) Approval Flow

When `require_approval: true`, the pipeline implements a **3-state state machine**:

```
running ──► awaiting_approval ──► (human reviews) ──► running ──► completed
                                                    └──► (rejected) ──► (no-op)
```

| Status | Meaning |
|---|---|
| `running` | Pipeline is actively executing stages |
| `awaiting_approval` | Paused after Logistics stage; council has NOT run yet |
| `completed` | All 4 stages done; council recommendation available |
| `failed` | An agent raised an exception; `error` key contains the message |

**In the Dashboard UI:** Check the `Require Human Approval` checkbox before clicking **Process Email**. A banner will appear with an **Approve & Continue** button once the logistics stage finishes.

---

## Data Persistence

The SQLite database is stored at `data/maverick.db` and is created automatically on first run.

### Database tables

| Table | Description |
|---|---|
| `patient_context` | Key-value patient facts (transport pref, doctor, family, schedule) |
| `appointment_history` | Structured appointment records per doctor |
| `audit_logs` | Chronological log of every agent call with status |

### Default seeded context (on first run)

| Key | Value |
|---|---|
| `preferred_transport` | Medical Transport Service |
| `father_doctor` | Dr. Patel |
| `father_condition` | neurological monitoring |
| `last_appointment` | May 1, 2025 |
| `family_members` | Sarah (daughter), Mike (son) |
| `wednesday_schedule` | Patrick has client calls 9AM-12PM, free after 1PM |

---

## Docker Deployment

### Build and run with Docker Compose

```bash
# Create your .env file first
cp .env.example .env
# Edit .env and add GROQ_API_KEY=gsk_...

# Start the API service
docker compose up --build
```

The API will be available at [http://localhost:8000](http://localhost:8000).

The SQLite database is persisted via a volume mount at `./data:/app/data`.

### Build the image manually

```bash
docker build -t maverick-ai .
docker run -p 8000:8000 --env-file .env maverick-ai
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'app'`
**Cause:** Running `python app/main.py` directly.  
**Fix:** Always use uvicorn from the project root:
```bash
uvicorn app.main:app --reload --port 8000
```

### `Address already in use` / port 8000 conflict
```bash
kill $(lsof -t -i:8000) 2>/dev/null
uvicorn app.main:app --reload --port 8000
```

### `GROQ_API_KEY` is missing or invalid
- Ensure `.env` file exists in the project root with `GROQ_API_KEY=gsk_...`
- Get a free key at [console.groq.com/keys](https://console.groq.com/keys)

### Frontend shows "● API offline"
- Make sure the backend server is running: `uvicorn app.main:app --reload --port 8000`
- Check the terminal running uvicorn for errors
- The frontend auto-pings `/api/health` every 12 seconds and updates the dot automatically
- Ensure you opened `http://localhost:8000/app` — **not** `frontend/index.html` as a file

### AgentScope `FutureWarning` about google-generativeai
This is suppressed automatically in `workflow.py`. If you see it, it's cosmetic only and does not affect functionality.

### SQLite database issues
The database is auto-created at `data/maverick.db`. If you want a fresh start:
```bash
rm data/maverick.db
# Restart the server — it will re-seed defaults automatically
```

---

## Agent Pydantic Models

Each agent validates its LLM output against a strict Pydantic schema:

| Agent | Model | Key Fields |
|---|---|---|
| `email_agent` | `EmailAnalysis` | `event_type`, `person`, `doctor?`, `old_time?`, `new_time?`, `transportation_required`, `urgency`, `summary` |
| `memory_agent` | `MemoryContext` | `doctor_known`, `preferred_transport`, `last_appointment`, `family_members`, `wednesday_availability`, `relevant_notes` |
| `logistics_agent` | `LogisticsAnalysis` | `conflict_detected`, `conflict_details`, `transportation_needs_rebooking`, `transportation_action`, `family_notification_required`, `family_members_to_notify`, `estimated_coordination_effort`, `action_items` |
| `council_agent` | `CouncilRecommendation` | `recommendation`, `reasoning`, `tradeoffs`, `priority_actions`, `risk_level`, `confidence_score` |

---

## Quick Start Summary

```bash
# 1. Clone & enter the project
git clone https://github.com/iampraneeth1116/Assignment.git
cd Assignment

# 2. Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your Groq API key
echo "GROQ_API_KEY=gsk_your_key_here" > .env

# 5. Start the backend
uvicorn app.main:app --reload --port 8000

# 6. Open the frontend dashboard in your browser
open http://localhost:8000/app

# 7. Verify everything works
curl http://localhost:8000/api/health
```

Then visit [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API explorer. 🚀
