from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .diagnostics import analyze_telemetry
from .models import (
    DiagnosticResult,
    EvalReport,
    Feedback,
    FeedbackCreate,
    TelemetrySample,
    Ticket,
    TicketCreate,
    TicketStatus,
    TicketUpdate,
    TroubleshootingRequest,
    TroubleshootingResult,
)
from .session_store import TroubleshootingSessionStore
from .storage import create_ticket_store
from .troubleshooting import guide_troubleshooting


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DB_URL = os.getenv("TICKET_DB_URL")
DB_PATH = os.getenv("TICKET_DB_PATH", "./data/generated/tickets.sqlite3")
REDIS_URL = os.getenv("TROUBLESHOOTING_REDIS_URL")
SESSION_TTL_SECONDS = int(os.getenv("TROUBLESHOOTING_SESSION_TTL_SECONDS", "1800"))
STATIC_DIR = ROOT / "static"
store = create_ticket_store(db_url=DB_URL, db_path=DB_PATH)
session_store = TroubleshootingSessionStore(redis_url=REDIS_URL, ttl_seconds=SESSION_TTL_SECONDS)
db_backend = "postgresql" if DB_URL else "sqlite"

app = FastAPI(
    title="IoT Support Assistant Ticket Service",
    description="Local ticket and feedback service for low-confidence IoT support questions.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": db_backend, "session_memory": session_store.backend}


@app.post("/tickets/create", response_model=Ticket)
def create_ticket(payload: TicketCreate) -> Ticket:
    return store.create_ticket(payload)


@app.get("/tickets", response_model=list[Ticket])
def list_tickets(status: TicketStatus | None = Query(default=None)) -> list[Ticket]:
    return store.list_tickets(status=status)


@app.post("/tickets/{ticket_id}/status", response_model=Ticket)
def update_ticket_status(ticket_id: str, payload: TicketUpdate) -> Ticket:
    ticket = store.update_ticket_status(ticket_id, payload.status)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post("/feedback", response_model=Feedback)
def create_feedback(payload: FeedbackCreate) -> Feedback:
    return store.create_feedback(payload)


@app.get("/eval/report", response_model=EvalReport)
def get_eval_report() -> EvalReport:
    return store.eval_report()


@app.post("/diagnostics/analyze", response_model=DiagnosticResult)
def analyze_device(payload: TelemetrySample) -> DiagnosticResult:
    return analyze_telemetry(payload)


@app.post("/diagnostics/create-ticket", response_model=Ticket)
def create_ticket_from_diagnosis(payload: TelemetrySample) -> Ticket:
    diagnosis = analyze_telemetry(payload)
    if diagnosis.ticket_payload is None:
        raise HTTPException(status_code=400, detail="Diagnosis does not require a ticket")
    return store.create_ticket(diagnosis.ticket_payload)


@app.post("/troubleshooting/next", response_model=TroubleshootingResult)
def next_troubleshooting_step(payload: TroubleshootingRequest) -> TroubleshootingResult:
    merged_payload = session_store.merge(payload)
    result = guide_troubleshooting(merged_payload)
    result.session_id = merged_payload.session_id
    session_store.save_result(merged_payload)
    return result


@app.post("/troubleshooting/create-ticket", response_model=Ticket)
def create_ticket_from_troubleshooting(payload: TroubleshootingRequest) -> Ticket:
    merged_payload = session_store.merge(payload)
    result = guide_troubleshooting(merged_payload)
    if result.ticket_payload is None:
        raise HTTPException(status_code=400, detail="Troubleshooting result does not require a ticket")
    return store.create_ticket(result.ticket_payload)
