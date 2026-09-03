from __future__ import annotations

import os
from pathlib import Path

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
from .storage import TicketStore
from .troubleshooting import guide_troubleshooting


DB_PATH = os.getenv("TICKET_DB_PATH", "./data/generated/tickets.sqlite3")
ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
store = TicketStore(DB_PATH)

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
    return {"status": "ok"}


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
    return guide_troubleshooting(payload)


@app.post("/troubleshooting/create-ticket", response_model=Ticket)
def create_ticket_from_troubleshooting(payload: TroubleshootingRequest) -> Ticket:
    result = guide_troubleshooting(payload)
    if result.ticket_payload is None:
        raise HTTPException(status_code=400, detail="Troubleshooting result does not require a ticket")
    return store.create_ticket(result.ticket_payload)
