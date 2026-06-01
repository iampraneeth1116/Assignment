# Maverick — AI Care-Coordination Assistant

Maverick is a multi-agent personal assistant for **Patrick**, helping coordinate his father's medical appointments, transport, and care logistics — powered by **Groq (LLaMA 3.3-70B)** and FastAPI.

---

## Architecture

```
User / Frontend
      │
      ▼
 FastAPI  (/api/*)
      │
      ▼
 council_agent   ← orchestrator (routes + synthesises)
  ├── memory_agent    – reads/writes patient context (SQLite)
  ├── logistics_agent – appointment scheduling & transport
  └── email_agent     – drafts professional emails
      │
      ▼
 MemoryStore + AuditLog  (data/maverick.db)
```

---

## Setup

### 1. Clone & create `.env`
```bash
cp .env.example .env
# Edit .env and add your Groq API key: GROQ_API_KEY=gsk_...
```

### 2. Install dependencies (virtual env recommended)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the API server
```bash
uvicorn app.main:app --reload
```

API docs available at **http://localhost:8000/docs**

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/query` | Send a natural-language request to Maverick |
| `GET`  | `/api/context` | Get all stored patient context |
| `POST` | `/api/context` | Set / update a context key |
| `GET`  | `/api/appointments/{doctor}` | Get appointment history for a doctor |
| `POST` | `/api/appointments` | Manually log an appointment |
| `GET`  | `/api/audit/logs` | Get all audit log entries |
| `GET`  | `/api/audit/logs/{agent_name}` | Get audit logs for a specific agent |
| `GET`  | `/api/health` | Health check |

### Example — Query Maverick
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Schedule an appointment with Dr. Patel next Wednesday afternoon"}'
```

---

## Database

SQLite DB is stored at `data/maverick.db` (created automatically on first run).

**Tables:**
- `patient_context` — key/value store for preferences and facts
- `appointment_history` — structured appointment records
- `audit_logs` — per-agent invocation log

**Default seeded context:**

| Key | Value |
|-----|-------|
| `preferred_transport` | Medical Transport Service |
| `father_doctor` | Dr. Patel |
| `father_condition` | neurological monitoring |
| `last_appointment` | May 1, 2025 |
| `family_members` | Sarah (daughter), Mike (son) |
| `wednesday_schedule` | Patrick has client calls 9AM-12PM, free after 1PM |

---

## Docker

```bash
docker compose up --build
```

- API → http://localhost:8000
- Frontend → http://localhost:3000

---

## Project Structure

```
maverick-assignment/
├── app/
│   ├── agents/
│   │   ├── council_agent.py    # Orchestrator
│   │   ├── memory_agent.py     # Context R/W
│   │   ├── logistics_agent.py  # Scheduling & transport
│   │   └── email_agent.py      # Email drafting
│   ├── graph/
│   │   └── workflow.py         # Agent graph & state
│   ├── api/
│   │   └── routes.py           # FastAPI routes
│   ├── memory/
│   │   └── memory_store.py     # SQLite context store
│   ├── audit/
│   │   └── audit_log.py        # SQLite audit log
│   └── main.py                 # FastAPI app factory
├── frontend/
│   └── index.html              # Simple chat UI
├── data/                       # SQLite DB (auto-created)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```
