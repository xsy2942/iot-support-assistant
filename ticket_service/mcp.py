from __future__ import annotations

import json
from typing import Any

from .agent import SupportAgent
from .agent_memory import AgentMemoryStore
from .models import AgentRequest, TicketCreate


class McpToolServer:
    """Compatibility JSON-RPC endpoint. The official MCP SDK server lives in mcp_server.py."""

    def __init__(self, agent: SupportAgent, ticket_store: Any, memory_store: AgentMemoryStore) -> None:
        self.agent = agent
        self.ticket_store = ticket_store
        self.memory_store = memory_store

    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        method = message.get("method")
        request_id = message.get("id")
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": message.get("params", {}).get("protocolVersion", "2025-06-18"),
                    "serverInfo": {"name": "iot-support-agent", "version": "0.2.0"},
                    "capabilities": {"tools": {}},
                }
            elif method == "tools/list":
                result = {"tools": self._tools()}
            elif method == "tools/call":
                result = self._call_tool(message.get("params", {}))
            elif method == "ping":
                result = {}
            else:
                return self._error(request_id, -32601, f"Unknown method: {method}")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:  # pragma: no cover - JSON-RPC error path
            return self._error(request_id, -32000, str(exc))

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name == "agent.respond":
            request = self.memory_store.merge(AgentRequest(**arguments))
            response = self.agent.respond(request)
            self.memory_store.save_turn(request, response)
            return self._text_result(response.model_dump(mode="json"))
        if name == "knowledge.search":
            hits = self.agent.knowledge_base.search(arguments["query"], top_k=arguments.get("top_k", 3))
            return self._text_result([hit.__dict__ for hit in hits])
        if name == "tickets.create":
            ticket = self.ticket_store.create_ticket(TicketCreate(**arguments))
            return self._text_result(ticket.model_dump(mode="json"))
        raise ValueError(f"Unknown tool: {name}")

    @staticmethod
    def _tools() -> list[dict[str, Any]]:
        return [
            {
                "name": "agent.respond",
                "description": "Run the IoT support Agent. It can clarify missing facts, retrieve local evidence, or prepare handoff tickets.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "session_id": {"type": "string"},
                        "device_model": {"type": "string"},
                        "error_code": {"type": "string"},
                        "network_type": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 8},
                    },
                    "required": ["question"],
                },
            },
            {
                "name": "knowledge.search",
                "description": "Search local IoT support knowledge chunks with child-to-parent routed retrieval.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 8},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "tickets.create",
                "description": "Create a local support ticket after the Agent decides human review is needed.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "summary": {"type": "string"},
                        "category": {"type": "string"},
                        "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                        "device_model": {"type": "string"},
                        "error_code": {"type": "string"},
                        "retrieved_sources": {"type": "array", "items": {"type": "string"}},
                        "suggested_action": {"type": "string"},
                    },
                    "required": ["question", "summary"],
                },
            },
        ]

    @staticmethod
    def _text_result(data: Any) -> dict[str, Any]:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(data, ensure_ascii=False, default=str),
                }
            ],
            "isError": False,
        }

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
