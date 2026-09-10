from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TicketStatus(str, Enum):
    open = "open"
    reviewing = "reviewing"
    resolved = "resolved"
    closed = "closed"


class Priority(str, Enum):
    p1 = "P1"
    p2 = "P2"
    p3 = "P3"


class Route(str, Enum):
    direct_answer = "direct_answer"
    review = "review"
    handoff = "handoff"


class AgentRoute(str, Enum):
    clarify = "clarify"
    rag_answer = "rag_answer"
    diagnostic = "diagnostic"
    handoff = "handoff"


class AgentStatus(str, Enum):
    complete = "COMPLETE"
    partial = "PARTIAL"
    unknown = "UNKNOWN"
    incomplete = "INCOMPLETE"


class TicketCreate(BaseModel):
    question: str = Field(min_length=2)
    device_model: str | None = None
    firmware_version: str | None = None
    error_code: str | None = None
    category: str = "uncategorized"
    priority: Priority = Priority.p2
    summary: str
    retrieved_sources: list[str] = Field(default_factory=list)
    suggested_action: str = "human review recommended"


class Ticket(TicketCreate):
    ticket_id: str
    status: TicketStatus = TicketStatus.open
    created_at: datetime
    updated_at: datetime


class TicketUpdate(BaseModel):
    status: TicketStatus


class FeedbackCreate(BaseModel):
    question: str
    answer: str
    useful: bool
    ticket_id: str | None = None
    comment: str | None = None
    retrieved_sources: list[str] = Field(default_factory=list)


class Feedback(FeedbackCreate):
    feedback_id: str
    created_at: datetime


class EvalReport(BaseModel):
    ticket_count: int
    open_ticket_count: int
    feedback_count: int
    useful_feedback_rate: float


class TelemetrySample(BaseModel):
    sample_id: str
    timestamp: datetime
    device_id: str
    product_line: str
    device_model: str
    firmware_version: str
    online: bool
    mqtt_connected: bool
    heartbeat_age_sec: int = Field(ge=0)
    rssi_dbm: int
    battery_percent: int = Field(ge=0, le=100)
    temperature_c: float
    humidity_percent: float = Field(ge=0, le=100)
    vibration_mm_s: float = Field(ge=0)
    voltage_v: float = Field(ge=0)
    error_code: str | None = None
    last_upgrade_status: str = "idle"
    customer_risk_signal: str | None = None


class DiagnosticFinding(BaseModel):
    category: str
    severity: str
    evidence: str
    action: str


class DiagnosticResult(BaseModel):
    sample_id: str
    device_id: str
    category: str
    priority: Priority
    route: Route
    confidence_score: float = Field(ge=0, le=1)
    findings: list[DiagnosticFinding]
    ticket_payload: TicketCreate | None = None


class TroubleshootingRequest(BaseModel):
    session_id: str | None = None
    question: str = Field(min_length=2)
    issue_type: str | None = None
    device_model: str | None = None
    error_code: str | None = None
    online_status: str | None = None
    indicator_light: str | None = None
    network_type: str | None = None
    heartbeat_age_sec: int | None = Field(default=None, ge=0)
    mqtt_connected: bool | None = None
    last_upgrade_status: str | None = None
    tried_steps: list[str] = Field(default_factory=list)
    risk_signal: str | None = None


class TroubleshootingQuestion(BaseModel):
    field: str
    question: str
    options: list[str] = Field(default_factory=list)


class TroubleshootingResult(BaseModel):
    session_id: str | None = None
    issue_type: str
    route: Route
    priority: Priority
    confidence_score: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    follow_up_questions: list[TroubleshootingQuestion] = Field(default_factory=list)
    collected_facts: dict[str, str] = Field(default_factory=dict)
    suggested_action: str
    ticket_payload: TicketCreate | None = None


class AgentRequest(BaseModel):
    question: str = Field(min_length=2)
    session_id: str | None = None
    issue_type: str | None = None
    device_model: str | None = None
    firmware_version: str | None = None
    error_code: str | None = None
    online_status: str | None = None
    indicator_light: str | None = None
    network_type: str | None = None
    heartbeat_age_sec: int | None = Field(default=None, ge=0)
    mqtt_connected: bool | None = None
    last_upgrade_status: str | None = None
    tried_steps: list[str] = Field(default_factory=list)
    risk_signal: str | None = None
    top_k: int = Field(default=3, ge=1, le=8)


class AgentStep(BaseModel):
    index: int
    name: str
    tool: str
    reason: str
    status: str = "pending"


class AgentEvidence(BaseModel):
    source_id: str
    source_type: str
    title: str
    score: float = Field(ge=0)
    quote: str
    metadata: dict[str, str] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    route: AgentRoute
    status: AgentStatus
    answer: str
    confidence_score: float = Field(ge=0, le=1)
    plan: list[AgentStep]
    evidence: list[AgentEvidence] = Field(default_factory=list)
    follow_up_questions: list[TroubleshootingQuestion] = Field(default_factory=list)
    ticket_payload: TicketCreate | None = None
