from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import EvalReport, Feedback, FeedbackCreate, Ticket, TicketCreate, TicketStatus


class SqliteTicketStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    device_model TEXT,
                    firmware_version TEXT,
                    error_code TEXT,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    retrieved_sources TEXT NOT NULL,
                    suggested_action TEXT NOT NULL,
                    attachments TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_sqlite_column(connection, "tickets", "attachments", "TEXT NOT NULL DEFAULT '[]'")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    useful INTEGER NOT NULL,
                    ticket_id TEXT,
                    comment TEXT,
                    retrieved_sources TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def create_ticket(self, payload: TicketCreate) -> Ticket:
        now = datetime.now()
        ticket = Ticket(
            **payload.model_dump(),
            ticket_id=f"T-{now:%Y%m%d}-{uuid4().hex[:8].upper()}",
            status=TicketStatus.open,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tickets (
                    ticket_id, question, device_model, firmware_version, error_code,
                    category, priority, summary, retrieved_sources, suggested_action,
                    attachments, status, created_at, updated_at
                )
                VALUES (
                    :ticket_id, :question, :device_model, :firmware_version, :error_code,
                    :category, :priority, :summary, :retrieved_sources, :suggested_action,
                    :attachments, :status, :created_at, :updated_at
                )
                """,
                self._ticket_to_row(ticket),
            )
        return ticket

    def list_tickets(self, status: TicketStatus | None = None) -> list[Ticket]:
        query = "SELECT * FROM tickets"
        params: tuple[str, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_ticket(row) for row in rows]

    def update_ticket_status(self, ticket_id: str, status: TicketStatus) -> Ticket | None:
        now = datetime.now().isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
                (status.value, now, ticket_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        return self._row_to_ticket(row)

    def create_feedback(self, payload: FeedbackCreate) -> Feedback:
        feedback = Feedback(
            **payload.model_dump(),
            feedback_id=f"F-{uuid4().hex[:10].upper()}",
            created_at=datetime.now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO feedback VALUES (
                    :feedback_id, :question, :answer, :useful, :ticket_id,
                    :comment, :retrieved_sources, :created_at
                )
                """,
                {
                    **feedback.model_dump(),
                    "useful": int(feedback.useful),
                    "retrieved_sources": json.dumps(feedback.retrieved_sources, ensure_ascii=False),
                    "created_at": feedback.created_at.isoformat(),
                },
            )
        return feedback

    def eval_report(self) -> EvalReport:
        with self._connect() as connection:
            ticket_count = connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
            open_count = connection.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0]
            feedback_count = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            useful_count = connection.execute("SELECT COUNT(*) FROM feedback WHERE useful = 1").fetchone()[0]
        rate = round(useful_count / feedback_count, 4) if feedback_count else 0.0
        return EvalReport(
            ticket_count=ticket_count,
            open_ticket_count=open_count,
            feedback_count=feedback_count,
            useful_feedback_rate=rate,
        )

    @staticmethod
    def _ticket_to_row(ticket: Ticket) -> dict[str, object]:
        data = ticket.model_dump()
        data["priority"] = ticket.priority.value
        data["status"] = ticket.status.value
        data["retrieved_sources"] = json.dumps(ticket.retrieved_sources, ensure_ascii=False)
        data["attachments"] = json.dumps(data.get("attachments", []), ensure_ascii=False)
        data["created_at"] = ticket.created_at.isoformat()
        data["updated_at"] = ticket.updated_at.isoformat()
        return data

    @staticmethod
    def _row_to_ticket(row: sqlite3.Row) -> Ticket:
        data = dict(row)
        data["retrieved_sources"] = json.loads(data["retrieved_sources"])
        data["attachments"] = json.loads(data.get("attachments") or "[]")
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return Ticket(**data)

    @staticmethod
    def _ensure_sqlite_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


class PostgresTicketStore:
    def __init__(self, db_url: str) -> None:
        self.db_url = db_url
        self._init_db()

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL backend requires psycopg. Run: pip install -r requirements.txt") from exc
        return psycopg.connect(self.db_url, row_factory=dict_row)

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    device_model TEXT,
                    firmware_version TEXT,
                    error_code TEXT,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    retrieved_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                    suggested_action TEXT NOT NULL,
                    attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    useful BOOLEAN NOT NULL,
                    ticket_id TEXT,
                    comment TEXT,
                    retrieved_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS attachments JSONB NOT NULL DEFAULT '[]'::jsonb")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at DESC)")

    def create_ticket(self, payload: TicketCreate) -> Ticket:
        now = datetime.now()
        ticket = Ticket(
            **payload.model_dump(),
            ticket_id=f"T-{now:%Y%m%d}-{uuid4().hex[:8].upper()}",
            status=TicketStatus.open,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tickets (
                    ticket_id, question, device_model, firmware_version, error_code,
                    category, priority, summary, retrieved_sources, suggested_action,
                    attachments, status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    ticket.ticket_id,
                    ticket.question,
                    ticket.device_model,
                    ticket.firmware_version,
                    ticket.error_code,
                    ticket.category,
                    ticket.priority.value,
                    ticket.summary,
                    json.dumps(ticket.retrieved_sources, ensure_ascii=False),
                    ticket.suggested_action,
                    json.dumps(ticket.model_dump().get("attachments", []), ensure_ascii=False),
                    ticket.status.value,
                    ticket.created_at,
                    ticket.updated_at,
                ),
            )
        return ticket

    def list_tickets(self, status: TicketStatus | None = None) -> list[Ticket]:
        params: tuple[str, ...] = ()
        query = "SELECT * FROM tickets"
        if status:
            query += " WHERE status = %s"
            params = (status.value,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_ticket(row) for row in rows]

    def update_ticket_status(self, ticket_id: str, status: TicketStatus) -> Ticket | None:
        now = datetime.now()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE tickets SET status = %s, updated_at = %s WHERE ticket_id = %s",
                (status.value, now, ticket_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,)).fetchone()
        return self._row_to_ticket(row)

    def create_feedback(self, payload: FeedbackCreate) -> Feedback:
        feedback = Feedback(
            **payload.model_dump(),
            feedback_id=f"F-{uuid4().hex[:10].upper()}",
            created_at=datetime.now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO feedback (
                    feedback_id, question, answer, useful, ticket_id,
                    comment, retrieved_sources, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    feedback.feedback_id,
                    feedback.question,
                    feedback.answer,
                    feedback.useful,
                    feedback.ticket_id,
                    feedback.comment,
                    json.dumps(feedback.retrieved_sources, ensure_ascii=False),
                    feedback.created_at,
                ),
            )
        return feedback

    def eval_report(self) -> EvalReport:
        with self._connect() as connection:
            ticket_count = connection.execute("SELECT COUNT(*) AS count FROM tickets").fetchone()["count"]
            open_count = connection.execute("SELECT COUNT(*) AS count FROM tickets WHERE status = 'open'").fetchone()["count"]
            feedback_count = connection.execute("SELECT COUNT(*) AS count FROM feedback").fetchone()["count"]
            useful_count = connection.execute("SELECT COUNT(*) AS count FROM feedback WHERE useful = TRUE").fetchone()["count"]
        rate = round(useful_count / feedback_count, 4) if feedback_count else 0.0
        return EvalReport(
            ticket_count=ticket_count,
            open_ticket_count=open_count,
            feedback_count=feedback_count,
            useful_feedback_rate=rate,
        )

    @staticmethod
    def _row_to_ticket(row: dict[str, Any]) -> Ticket:
        data = dict(row)
        data["retrieved_sources"] = _sources(data["retrieved_sources"])
        data["attachments"] = _sources(data.get("attachments", []))
        return Ticket(**data)


def create_ticket_store(db_url: str | None = None, db_path: str | Path | None = None):
    if db_url:
        return PostgresTicketStore(db_url)
    return SqliteTicketStore(db_path or "./data/generated/tickets.sqlite3")


def _sources(value: Any) -> list[str]:
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, list):
        return value
    return list(value or [])


TicketStore = SqliteTicketStore
