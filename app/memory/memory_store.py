"""
memory_store.py
---------------
Persistent key/value store and appointment history backed by SQLite.
DB file: data/maverick.db (created automatically relative to the project root).
"""

import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve the DB path relative to the project root (two levels above this file:
#   app/memory/memory_store.py  →  project_root/data/maverick.db
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = _PROJECT_ROOT / "data" / "maverick.db"

_DEFAULT_CONTEXT: dict[str, str] = {
    "preferred_transport": "Medical Transport Service",
    "father_doctor": "Dr. Patel",
    "father_condition": "neurological monitoring",
    "last_appointment": "May 1, 2025",
    "family_members": "Sarah (daughter), Mike (son)",
    "wednesday_schedule": "Patrick has client calls 9AM-12PM, free after 1PM",
}


def _get_connection() -> sqlite3.Connection:
    """Return a new connection with row_factory set to sqlite3.Row."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


class MemoryStore:
    """
    Manages persistent context and appointment history for the Maverick agent.

    Tables
    ------
    patient_context     – arbitrary key/value pairs (e.g. preferences, facts)
    appointment_history – structured appointment records
    """

    def __init__(self) -> None:
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables and seed defaults on first run."""
        with _get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patient_context (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    key        TEXT    NOT NULL UNIQUE,
                    value      TEXT    NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS appointment_history (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor     TEXT    NOT NULL,
                    date       TEXT    NOT NULL,
                    notes      TEXT,
                    created_at TIMESTAMP NOT NULL
                )
            """)
            conn.commit()

            # Seed defaults only if the table is empty
            row = conn.execute("SELECT COUNT(*) as cnt FROM patient_context").fetchone()
            if row["cnt"] == 0:
                self._seed_defaults(conn)

    def _seed_defaults(self, conn: sqlite3.Connection) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO patient_context (key, value, updated_at) VALUES (?, ?, ?)",
            [(k, v, now) for k, v in _DEFAULT_CONTEXT.items()],
        )
        conn.commit()

    # ------------------------------------------------------------------
    # patient_context methods
    # ------------------------------------------------------------------

    def get_context(self, key: str) -> str | None:
        """Return the value for *key*, or ``None`` if it does not exist."""
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM patient_context WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def set_context(self, key: str, value: str) -> None:
        """Insert or update a context entry."""
        now = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO patient_context (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value      = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
            conn.commit()

    def get_all_context(self) -> dict[str, str]:
        """Return all context entries as a plain dict."""
        with _get_connection() as conn:
            rows = conn.execute(
                "SELECT key, value FROM patient_context"
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    # ------------------------------------------------------------------
    # appointment_history methods
    # ------------------------------------------------------------------

    def add_appointment(self, doctor: str, date: str, notes: str) -> None:
        """Append a new appointment record."""
        now = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO appointment_history (doctor, date, notes, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (doctor, date, notes, now),
            )
            conn.commit()

    def get_appointments(self, doctor: str) -> list[dict]:
        """Return all appointments for *doctor*, ordered by date descending."""
        with _get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, doctor, date, notes, created_at
                FROM appointment_history
                WHERE doctor = ?
                ORDER BY date DESC
                """,
                (doctor,),
            ).fetchall()
        return [dict(row) for row in rows]
