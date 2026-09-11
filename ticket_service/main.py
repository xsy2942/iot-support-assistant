from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agent_memory import AgentMemoryStore
from .diagnostics import analyze_telemetry
from .mcp import McpToolServer
from .models import (
    AgentRequest,
    AgentResponse,
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
from .react_agent import ReActSupportAgent
from .session_store import TroubleshootingSessionStore
from .storage import create_ticket_store
from .troubleshooting import guide_troubleshooting


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DB_URL = os.getenv("TICKET_DB_URL")
DB_PATH = os.getenv("TICKET_DB_PATH", "./data/generated/tickets.sqlite3")
REDIS_URL = os.getenv("TROUBLESHOOTING_REDIS_URL")
AGENT_MEMORY_REDIS_URL = os.getenv("AGENT_MEMORY_REDIS_URL", REDIS_URL or "")
SESSION_TTL_SECONDS = int(os.getenv("TROUBLESHOOTING_SESSION_TTL_SECONDS", "1800"))
AGENT_MEMORY_TTL_SECONDS = int(os.getenv("AGENT_MEMORY_TTL_SECONDS", str(SESSION_TTL_SECONDS)))
STATIC_DIR = ROOT / "static"
store = create_ticket_store(db_url=DB_URL, db_path=DB_PATH)
session_store = TroubleshootingSessionStore(redis_url=REDIS_URL, ttl_seconds=SESSION_TTL_SECONDS)
support_agent = ReActSupportAgent()
agent_memory_store = AgentMemoryStore(redis_url=AGENT_MEMORY_REDIS_URL, ttl_seconds=AGENT_MEMORY_TTL_SECONDS)
mcp_server = McpToolServer(agent=support_agent, ticket_store=store, memory_store=agent_memory_store)
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
    return {
        "status": "ok",
        "database": db_backend,
        "session_memory": session_store.backend,
        "agent_memory": agent_memory_store.backend,
    }


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


@app.post("/agent/respond", response_model=AgentResponse)
def respond_with_agent(payload: AgentRequest) -> AgentResponse:
    merged_payload = agent_memory_store.merge(payload)
    response = support_agent.respond(merged_payload)
    response.memory_facts = agent_memory_store.facts(merged_payload.session_id) or response.memory_facts
    agent_memory_store.save_turn(merged_payload, response)
    response.memory_facts = agent_memory_store.facts(merged_payload.session_id)
    return response


@app.get("/agent/memory/{session_id}")
def get_agent_memory(session_id: str) -> dict[str, Any]:
    return agent_memory_store.session(session_id)


@app.delete("/agent/memory/{session_id}")
def clear_agent_memory(session_id: str) -> dict[str, Any]:
    return {"session_id": session_id, "cleared": agent_memory_store.clear(session_id)}


@app.get("/agent/respond/stream")
def stream_agent_response(
    question: str,
    session_id: str | None = None,
    device_model: str | None = None,
    error_code: str | None = None,
    network_type: str | None = None,
    top_k: int = Query(default=3, ge=1, le=8),
) -> StreamingResponse:
    payload = AgentRequest(
        question=question,
        session_id=session_id,
        device_model=device_model,
        error_code=error_code,
        network_type=network_type,
        top_k=top_k,
    )

    def events():
        response = respond_with_agent(payload)
        for step in response.react_trace:
            yield _sse("step", step.model_dump())
        yield _sse("result", response.model_dump())

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/mcp")
def mcp_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    return mcp_server.handle(payload)


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


def _sse(event_name: str, data: Any) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
