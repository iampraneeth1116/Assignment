"""
audit_log.py
------------
Structured audit logging for every agent invocation, backed by the same
SQLite database used by MemoryStore (data/maverick.db).
"""

import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared DB path (mirrors the path in memory_store.py so both modules use
# the exact same file).
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = _PROJECT_ROOT / "data" / "maverick.db"


def _get_connection() -> sqlite3.Connection:
    """Return a new connection with row_factory set to sqlite3.Row."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


class AuditLog:
    """
    Records a timestamped entry for every agent call so the system has a
    full, queryable history of what each agent did and whether it succeeded.

    Table
    -----
    audit_logs – one row per agent invocation
    """

    def __init__(self) -> None:
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the audit_logs table if it doesn't already exist."""
        with _get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name     TEXT      NOT NULL,
                    timestamp      TIMESTAMP NOT NULL,
                    input_summary  TEXT,
                    output_summary TEXT,
                    status         TEXT      NOT NULL DEFAULT 'success'
                )
            """)
            conn.commit()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def log(
        self,
        agent_name: str,
        input_summary: str,
        output_summary: str,
        status: str = "success",
    ) -> None:
        """
        Append one audit entry.

        Parameters
        ----------
        agent_name:     Identifier of the agent being logged (e.g. ``"scheduler_agent"``).
        input_summary:  Short description of what the agent received as input.
        output_summary: Short description of what the agent produced/returned.
        status:         ``"success"`` (default), ``"error"``, ``"skipped"``, etc.
        """
        now = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs
                    (agent_name, timestamp, input_summary, output_summary, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (agent_name, now, input_summary, output_summary, status),
            )
            conn.commit()

    def get_logs(self) -> list[dict]:
        """Return all audit entries ordered by timestamp descending."""
        with _get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, agent_name, timestamp, input_summary, output_summary, status
                FROM audit_logs
                ORDER BY timestamp DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_logs_for_agent(self, agent_name: str) -> list[dict]:
        """Return all audit entries for a specific *agent_name*, newest first."""
        with _get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, agent_name, timestamp, input_summary, output_summary, status
                FROM audit_logs
                WHERE agent_name = ?
                ORDER BY timestamp DESC
                """,
                (agent_name,),
            ).fetchall()
        return [dict(row) for row in rows]
