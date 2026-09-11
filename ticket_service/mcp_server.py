from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from .agent import SupportAgent
from .agent_memory import AgentMemoryStore
from .models import AgentRequest, TicketCreate
from .storage import create_ticket_store


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def build_mcp_server(
    agent: SupportAgent | None = None,
    memory_store: AgentMemoryStore | None = None,
    ticket_store: Any | None = None,
) -> MCPServer:
    support_agent = agent or SupportAgent()
    agent_memory = memory_store or AgentMemoryStore(
        redis_url=os.getenv("AGENT_MEMORY_REDIS_URL") or os.getenv("TROUBLESHOOTING_REDIS_URL") or None,
        ttl_seconds=int(os.getenv("AGENT_MEMORY_TTL_SECONDS", "1800")),
    )
    tickets = ticket_store or create_ticket_store(
        db_url=os.getenv("TICKET_DB_URL") or None,
        db_path=os.getenv("TICKET_DB_PATH", "./data/generated/tickets.sqlite3"),
    )

    server = MCPServer(
        name="iot-support-agent",
        title="IoT Support Agent MCP Server",
        description="Official MCP server for IoT troubleshooting, local RAG retrieval, memory, and ticket handoff.",
        instructions=(
            "Use this server to answer IoT support questions with evidence. "
            "Clarify missing device facts, search local knowledge chunks, and create tickets only when human review is needed."
        ),
        version="0.3.0",
        dependencies=["mcp>=2.2.0", "fastapi", "scikit-learn", "redis", "psycopg"],
    )

    @server.tool(
        name="agent_respond",
        title="Run IoT Support Agent",
        description="Route an IoT support question through memory, troubleshooting, local RAG retrieval, verifier, and ticket handoff.",
        structured_output=True,
    )
    def agent_respond(
        question: str,
        session_id: str | None = None,
        issue_type: str | None = None,
        device_model: str | None = None,
        firmware_version: str | None = None,
        error_code: str | None = None,
        online_status: str | None = None,
        indicator_light: str | None = None,
        network_type: str | None = None,
        heartbeat_age_sec: int | None = None,
        mqtt_connected: bool | None = None,
        last_upgrade_status: str | None = None,
        risk_signal: str | None = None,
        top_k: int = 3,
    ) -> dict[str, Any]:
        request = agent_memory.merge(
            AgentRequest(
                question=question,
                session_id=session_id,
                issue_type=issue_type,
                device_model=device_model,
                firmware_version=firmware_version,
                error_code=error_code,
                online_status=online_status,
                indicator_light=indicator_light,
                network_type=network_type,
                heartbeat_age_sec=heartbeat_age_sec,
                mqtt_connected=mqtt_connected,
                last_upgrade_status=last_upgrade_status,
                risk_signal=risk_signal,
                top_k=top_k,
            )
        )
        response = support_agent.respond(request)
        agent_memory.save_turn(request, response)
        response.memory_facts = agent_memory.facts(request.session_id)
        return response.model_dump(mode="json")

    @server.tool(
        name="knowledge_search",
        title="Search IoT Knowledge Base",
        description="Search local IoT knowledge chunks with hybrid retrieval and parent-child evidence routing.",
        structured_output=True,
    )
    def knowledge_search(query: str, top_k: int = 3) -> dict[str, Any]:
        hits = support_agent.knowledge_base.search(query, top_k=top_k)
        return {
            "query": query,
            "top_k": top_k,
            "hits": [
                {
                    "parent_id": hit.parent_id,
                    "child_id": hit.child_id,
                    "chunk_id": hit.chunk_id,
                    "source_type": hit.source_type,
                    "title": hit.title,
                    "device_model": hit.device_model,
                    "error_code": hit.error_code,
                    "issue_type": hit.issue_type,
                    "score": hit.score,
                    "content": hit.content,
                    "sibling_count": hit.sibling_count,
                }
                for hit in hits
            ],
        }

    @server.tool(
        name="ticket_create",
        title="Create Support Ticket",
        description="Create a support ticket after the Agent determines that human review or handoff is required.",
        structured_output=True,
    )
    def ticket_create(
        question: str,
        summary: str,
        category: str = "agent_handoff",
        priority: str = "P2",
        device_model: str | None = None,
        firmware_version: str | None = None,
        error_code: str | None = None,
        suggested_action: str = "human review recommended",
    ) -> dict[str, Any]:
        ticket = tickets.create_ticket(
            TicketCreate(
                question=question,
                device_model=device_model,
                firmware_version=firmware_version,
                error_code=error_code,
                category=category,
                priority=priority,
                summary=summary,
                retrieved_sources=["mcp_tool"],
                suggested_action=suggested_action,
            )
        )
        return ticket.model_dump(mode="json")

    @server.resource(
        "iot://knowledge/summary",
        name="knowledge_summary",
        title="IoT Knowledge Summary",
        description="Summary of the local IoT support knowledge base.",
        mime_type="text/plain",
    )
    def knowledge_summary() -> str:
        rows = support_agent.knowledge_base.rows
        source_counts: dict[str, int] = {}
        for row in rows:
            source_type = row.get("source_type", "unknown")
            source_counts[source_type] = source_counts.get(source_type, 0) + 1
        return f"knowledge_chunks={len(rows)}; source_counts={source_counts}"

    @server.prompt(
        name="iot_support_prompt",
        title="IoT Support Prompt",
        description="Prompt template for evidence-based IoT troubleshooting.",
    )
    def iot_support_prompt(question: str) -> str:
        return (
            "你是 IoT 设备售后支持 Agent。必须先判断信息是否完整，再基于本地知识库证据回答。"
            "如果缺少设备型号、错误码、在线状态、网络类型等关键字段，先追问。"
            "如果涉及投诉、赔偿、安全事故或数据丢失，转人工并生成工单草稿。"
            f"用户问题：{question}"
        )

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the official MCP server for IoT Support Agent.")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--path", default="/mcp")
    args = parser.parse_args()

    server = build_mcp_server()
    if args.transport == "streamable-http":
        server.run("streamable-http", host=args.host, port=args.port, streamable_http_path=args.path)
    elif args.transport == "sse":
        server.run("sse", host=args.host, port=args.port)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
