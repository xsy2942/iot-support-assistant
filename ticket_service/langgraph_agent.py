from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .knowledge_base import KnowledgeBase, KnowledgeHit
from .llm_provider import OpenAIChatToolModel
from .models import (
    AgentEvidence,
    AgentRequest,
    AgentResponse,
    AgentRoute,
    AgentStatus,
    Priority,
    ReactTraceStep,
    TicketCreate,
    TroubleshootingRequest,
    TroubleshootingResult,
)
from .react_agent import ReActSupportAgent
from .troubleshooting import guide_troubleshooting


SYSTEM_PROMPT = """你是 IoT 设备售后支持 Agent 的规划器。你的职责是根据用户问题和工具观察结果，自主选择下一项工具，而不是直接输出普通聊天答案。

执行规则：
1. 用户信息模糊时，先调用 inspect_support_context；需要读取已知设备事实时可调用 read_session_memory。
2. 准备给出技术排障答案前，必须调用 search_iot_knowledge 获取证据，不得编造来源编号。
3. 涉及投诉、赔偿、冒烟、起火、安全事故或数据丢失时，必须先调用 draft_support_ticket，再以 handoff 路由结束。
4. 信息不足时以 clarify 路由结束；证据充分时以 rag_answer 路由结束；需要人工时以 handoff 路由结束。
5. 只有调用 finalize_support_response 才算完成。每轮根据最新 Observation 决定下一项工具，避免重复调用没有新信息的工具。
6. 回答使用中文，面向一线客服，给出简洁、可执行的步骤。不要输出隐藏思维过程。
"""


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_session_memory",
            "description": "读取本轮请求已经合并的会话事实，例如设备型号、错误码、在线状态和网络类型。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_support_context",
            "description": "检查问题属于哪类故障、缺少哪些关键字段，以及是否命中高风险人工边界。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_iot_knowledge",
            "description": "检索本地 IoT 售后知识库，返回可引用的 FAQ、错误码、手册和历史工单证据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "用于检索的完整问题"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 8},
                    "device_model": {"type": "string"},
                    "error_code": {"type": "string"},
                    "issue_type": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_support_ticket",
            "description": "为高风险、资料不足或需要二线工程师处理的问题生成工单草稿。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                    "summary": {"type": "string"},
                    "suggested_action": {"type": "string"},
                },
                "required": ["category", "priority", "summary", "suggested_action"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finalize_support_response",
            "description": "提交最终客服结论。程序会校验证据、风险边界、追问条件和工单草稿，不满足条件会拒绝完成。",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "enum": ["clarify", "rag_answer", "handoff"]},
                    "answer": {"type": "string"},
                    "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["route", "answer", "confidence_score"],
                "additionalProperties": False,
            },
        },
    },
]


class AgentGraphState(TypedDict, total=False):
    request: dict[str, Any]
    messages: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    evidence_hits: list[dict[str, Any]]
    troubleshooting: dict[str, Any] | None
    ticket_payload: dict[str, Any] | None
    final_response: dict[str, Any] | None
    iteration: int
    max_iterations: int


class LangGraphSupportAgent:
    """LangGraph runtime whose next action is selected by real LLM tool calls."""

    runtime_name = "langgraph-tool-calling"

    def __init__(
        self,
        model: OpenAIChatToolModel,
        knowledge_base: KnowledgeBase | None = None,
        fallback: ReActSupportAgent | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        self.model = model
        self.provider = model.settings.provider
        self.model_name = model.settings.model
        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.fallback = fallback or ReActSupportAgent(self.knowledge_base)
        self.checkpointer = checkpointer or InMemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        builder = StateGraph(AgentGraphState)
        builder.add_node("planner", self._planner_node)
        builder.add_node("tools", self._tools_node)
        builder.add_edge(START, "planner")
        builder.add_conditional_edges(
            "planner",
            self._after_planner,
            {"tools": "tools", "planner": "planner", "end": END},
        )
        builder.add_conditional_edges(
            "tools",
            self._after_tools,
            {"planner": "planner", "end": END},
        )
        return builder.compile(checkpointer=self.checkpointer)

    def respond(self, request: AgentRequest) -> AgentResponse:
        execution_id = f"{request.session_id or 'anonymous'}:{uuid4().hex}"
        initial_state: AgentGraphState = {
            "request": request.model_dump(mode="json"),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._user_message(request)},
            ],
            "pending_tool_calls": [],
            "trace": [],
            "evidence_hits": [],
            "troubleshooting": None,
            "ticket_payload": None,
            "final_response": None,
            "iteration": 0,
            "max_iterations": request.max_steps,
        }
        try:
            state = self.graph.invoke(
                initial_state,
                config={
                    "configurable": {"thread_id": execution_id},
                    "recursion_limit": max(30, request.max_steps * 4),
                },
            )
            if not state.get("final_response"):
                return self._fallback_response(
                    request,
                    state.get("trace", []),
                    execution_id,
                    f"LLM did not finalize within {request.max_steps} planning rounds",
                )
            response = AgentResponse.model_validate(state["final_response"])
            response.react_trace = self._reindex_trace(state.get("trace", []))
            response.plan = ReActSupportAgent._plan_from_trace(response.react_trace)
            response.runtime = self.runtime_name
            response.model_provider = self.provider
            response.model_name = self.model_name
            response.execution_id = execution_id
            return response
        except Exception as exc:
            return self._fallback_response(
                request,
                [],
                execution_id,
                f"{type(exc).__name__}: model or graph execution failed",
            )

    def _planner_node(self, state: AgentGraphState) -> AgentGraphState:
        completion = self.model.complete(state["messages"], TOOL_SCHEMAS)
        message = completion.choices[0].message
        content = message.content or ""
        calls = [self._normalize_tool_call(call) for call in (message.tool_calls or [])]
        iteration = state.get("iteration", 0) + 1
        assistant_message: dict[str, Any] = {"role": "assistant", "content": content}
        if calls:
            assistant_message["tool_calls"] = [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {"name": call["name"], "arguments": json.dumps(call["arguments"], ensure_ascii=False)},
                }
                for call in calls
            ]

        messages = [*state["messages"], assistant_message]
        if not calls and iteration < state["max_iterations"]:
            messages.append(
                {
                    "role": "user",
                    "content": "请不要直接输出普通文本。请选择合适工具；若已有结论，请调用 finalize_support_response。",
                }
            )
        trace = [
            *state.get("trace", []),
            ReactTraceStep(
                index=len(state.get("trace", [])) + 1,
                reasoning_summary="LLM 根据当前问题与工具观察结果规划下一步。",
                action="llm.plan",
                action_input={"planning_round": iteration},
                observation={
                    "selected_tools": [call["name"] for call in calls],
                    "returned_plain_text": bool(content),
                    "provider": self.provider,
                    "model": self.model_name,
                },
                next_decision="执行模型选择的工具。" if calls else "要求模型改用结构化工具调用。",
            ).model_dump(mode="json"),
        ]
        return {
            **state,
            "messages": messages,
            "pending_tool_calls": calls,
            "trace": trace,
            "iteration": iteration,
        }

    def _tools_node(self, state: AgentGraphState) -> AgentGraphState:
        working: AgentGraphState = {**state}
        messages = list(state["messages"])
        trace = list(state.get("trace", []))
        for call in state.get("pending_tool_calls", []):
            observation = self._execute_tool(call["name"], call["arguments"], working)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(observation, ensure_ascii=False, default=str),
                }
            )
            trace.append(
                ReactTraceStep(
                    index=len(trace) + 1,
                    reasoning_summary=self._tool_reason(call["name"]),
                    action=self._trace_action(call["name"], call["arguments"]),
                    action_input=call["arguments"],
                    observation=observation,
                    next_decision=(
                        "最终结果已通过程序校验。"
                        if working.get("final_response")
                        else "将 Observation 返回给 LLM，由模型决定下一项工具。"
                    ),
                ).model_dump(mode="json")
            )
            if working.get("final_response"):
                break
        return {
            **working,
            "messages": messages,
            "pending_tool_calls": [],
            "trace": trace,
        }

    @staticmethod
    def _after_planner(state: AgentGraphState) -> str:
        if state.get("pending_tool_calls"):
            return "tools"
        if state.get("iteration", 0) >= state.get("max_iterations", 1):
            return "end"
        return "planner"

    @staticmethod
    def _after_tools(state: AgentGraphState) -> str:
        if state.get("final_response") or state.get("iteration", 0) >= state.get("max_iterations", 1):
            return "end"
        return "planner"

    def _execute_tool(self, name: str, arguments: dict[str, Any], state: AgentGraphState) -> dict[str, Any]:
        request = AgentRequest.model_validate(state["request"])
        if name == "read_session_memory":
            facts = ReActSupportAgent._memory_facts(request)
            return {"ok": True, "facts": facts, "fact_count": len(facts)}

        if name == "inspect_support_context":
            risk_signal = ReActSupportAgent._risk_signal(request)
            result = guide_troubleshooting(
                TroubleshootingRequest(
                    session_id=request.session_id,
                    question=request.question,
                    issue_type=request.issue_type,
                    device_model=request.device_model,
                    error_code=request.error_code,
                    online_status=request.online_status,
                    indicator_light=request.indicator_light,
                    network_type=request.network_type,
                    heartbeat_age_sec=request.heartbeat_age_sec,
                    mqtt_connected=request.mqtt_connected,
                    last_upgrade_status=request.last_upgrade_status,
                    tried_steps=request.tried_steps,
                    risk_signal=risk_signal,
                )
            )
            state["troubleshooting"] = result.model_dump(mode="json")
            return {
                "ok": True,
                "issue_type": result.issue_type,
                "missing_fields": result.missing_fields,
                "follow_up_questions": [item.model_dump(mode="json") for item in result.follow_up_questions],
                "risk_signal": risk_signal,
                "recommended_route": result.route.value,
            }

        if name == "search_iot_knowledge":
            top_k = max(1, min(int(arguments.get("top_k", request.top_k)), 8))
            hits = self.knowledge_base.search(
                str(arguments.get("query") or request.question),
                top_k=top_k,
                device_model=str(arguments.get("device_model") or request.device_model or "") or None,
                error_code=str(arguments.get("error_code") or request.error_code or "") or None,
                issue_type=str(arguments.get("issue_type") or request.issue_type or "") or None,
            )
            state["evidence_hits"] = [asdict(hit) for hit in hits]
            return {
                "ok": True,
                "hit_count": len(hits),
                "hits": [
                    {
                        "source_id": hit.chunk_id,
                        "source_type": hit.source_type,
                        "title": hit.title,
                        "score": hit.score,
                        "content": hit.content[:600],
                        "route_path": f"{hit.parent_id} -> {hit.child_id}",
                    }
                    for hit in hits
                ],
            }

        if name == "draft_support_ticket":
            risk_signal = ReActSupportAgent._risk_signal(request)
            requested_priority = str(arguments.get("priority", "P2")).upper()
            priority = Priority.p1 if risk_signal else Priority(requested_priority if requested_priority in {"P1", "P2", "P3"} else "P2")
            hits = self._state_hits(state)
            payload = TicketCreate(
                question=request.question,
                device_model=request.device_model,
                firmware_version=request.firmware_version,
                error_code=request.error_code,
                category=str(arguments.get("category") or "agent_handoff"),
                priority=priority,
                summary=str(arguments.get("summary") or f"{request.device_model or '未知设备'}：{request.question[:100]}"),
                retrieved_sources=[hit.chunk_id for hit in hits],
                suggested_action=str(arguments.get("suggested_action") or "建议人工复核并保留现场日志。"),
                attachments=request.attachments,
            )
            state["ticket_payload"] = payload.model_dump(mode="json")
            return {
                "ok": True,
                "priority": payload.priority.value,
                "category": payload.category,
                "retrieved_sources": payload.retrieved_sources,
                "attachment_count": len(payload.attachments),
            }

        if name == "finalize_support_response":
            return self._finalize(arguments, state, request)

        return {"ok": False, "error": f"Unknown or unauthorized tool: {name}"}

    def _finalize(self, arguments: dict[str, Any], state: AgentGraphState, request: AgentRequest) -> dict[str, Any]:
        route_value = str(arguments.get("route", ""))
        if route_value not in {"clarify", "rag_answer", "handoff"}:
            return {"ok": False, "error": "route must be clarify, rag_answer, or handoff"}

        risk_signal = ReActSupportAgent._risk_signal(request)
        if risk_signal and route_value != "handoff":
            return {"ok": False, "error": f"High-risk signal {risk_signal} requires ticket draft and handoff"}

        hits = self._state_hits(state)
        selected_hits = hits
        requested_ids = [str(item) for item in arguments.get("source_ids", []) if item]
        if requested_ids:
            valid_by_id = {hit.chunk_id: hit for hit in hits}
            invalid_ids = [source_id for source_id in requested_ids if source_id not in valid_by_id]
            if invalid_ids:
                return {"ok": False, "error": "source_ids contain evidence that was not returned by knowledge search", "invalid_ids": invalid_ids}
            selected_hits = [valid_by_id[source_id] for source_id in requested_ids]

        troubleshooting = self._state_troubleshooting(state)
        if route_value == "rag_answer" and not selected_hits:
            return {"ok": False, "error": "rag_answer requires knowledge evidence; call search_iot_knowledge first"}
        if route_value == "clarify" and (troubleshooting is None or not troubleshooting.missing_fields):
            return {"ok": False, "error": "clarify requires missing fields from inspect_support_context"}
        if route_value == "handoff" and not state.get("ticket_payload"):
            return {"ok": False, "error": "handoff requires a ticket draft; call draft_support_ticket first"}

        answer = str(arguments.get("answer") or "").strip()
        if not answer:
            return {"ok": False, "error": "answer must not be empty"}
        if route_value == "rag_answer":
            source_ids = [hit.chunk_id for hit in selected_hits]
            if not all(source_id in answer for source_id in source_ids):
                answer += f"\n参考来源：{'、'.join(source_ids)}。"

        requested_confidence = self._confidence(arguments.get("confidence_score"))
        if route_value == "rag_answer":
            evidence_cap = min(0.95, 0.45 + max(hit.score for hit in selected_hits) * 0.6)
            confidence = min(requested_confidence, evidence_cap)
            status = AgentStatus.complete if selected_hits[0].score >= 0.25 else AgentStatus.partial
            route = AgentRoute.rag_answer
        elif route_value == "clarify":
            confidence = min(requested_confidence, 0.75)
            status = AgentStatus.incomplete
            route = AgentRoute.clarify
        else:
            confidence = min(requested_confidence, 0.9 if risk_signal else 0.65)
            status = AgentStatus.partial if risk_signal else AgentStatus.unknown
            route = AgentRoute.handoff

        response = AgentResponse(
            session_id=request.session_id,
            route=route,
            status=status,
            answer=answer,
            confidence_score=round(confidence, 3),
            plan=[],
            evidence=ReActSupportAgent._evidence(selected_hits),
            follow_up_questions=troubleshooting.follow_up_questions if troubleshooting else [],
            memory_facts=ReActSupportAgent._memory_facts(request),
            ticket_payload=TicketCreate.model_validate(state["ticket_payload"]) if state.get("ticket_payload") else None,
            runtime=self.runtime_name,
            model_provider=self.provider,
            model_name=self.model_name,
        )
        state["final_response"] = response.model_dump(mode="json")
        return {"ok": True, "route": route.value, "status": status.value, "confidence_score": response.confidence_score}

    def _fallback_response(
        self,
        request: AgentRequest,
        graph_trace: list[dict[str, Any]],
        execution_id: str,
        reason: str,
    ) -> AgentResponse:
        response = self.fallback.respond(request)
        combined = [*graph_trace, *[step.model_dump(mode="json") for step in response.react_trace]]
        response.react_trace = self._reindex_trace(combined)
        response.plan = ReActSupportAgent._plan_from_trace(response.react_trace)
        response.runtime = "deterministic-fallback"
        response.model_provider = self.provider
        response.model_name = self.model_name
        response.execution_id = execution_id
        response.fallback_reason = reason
        return response

    @staticmethod
    def _normalize_tool_call(call: Any) -> dict[str, Any]:
        raw_arguments = call.function.arguments or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        return {"id": call.id or uuid4().hex, "name": call.function.name, "arguments": arguments}

    @staticmethod
    def _user_message(request: AgentRequest) -> str:
        payload = request.model_dump(mode="json", exclude_none=True)
        return "请处理以下 IoT 售后请求，并通过工具完成：\n" + json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _state_hits(state: AgentGraphState) -> list[KnowledgeHit]:
        return [KnowledgeHit(**item) for item in state.get("evidence_hits", [])]

    @staticmethod
    def _state_troubleshooting(state: AgentGraphState) -> TroubleshootingResult | None:
        value = state.get("troubleshooting")
        return TroubleshootingResult.model_validate(value) if value else None

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(float(value), 1.0))
        except (TypeError, ValueError):
            return 0.5

    @staticmethod
    def _trace_action(tool_name: str, arguments: dict[str, Any]) -> str:
        if tool_name == "read_session_memory":
            return "memory.read"
        if tool_name == "inspect_support_context":
            return "troubleshooting.guide"
        if tool_name == "search_iot_knowledge":
            return "knowledge.search"
        if tool_name == "draft_support_ticket":
            return "ticket.draft"
        if tool_name == "finalize_support_response":
            return {
                "clarify": "final.clarify",
                "rag_answer": "final.answer",
                "handoff": "final.handoff",
            }.get(str(arguments.get("route")), "final.answer")
        return tool_name

    @staticmethod
    def _tool_reason(tool_name: str) -> str:
        return {
            "read_session_memory": "执行 LLM 选择的会话记忆读取工具。",
            "inspect_support_context": "执行 LLM 选择的信息完整度与风险检查工具。",
            "search_iot_knowledge": "执行 LLM 选择的本地知识库检索工具。",
            "draft_support_ticket": "执行 LLM 选择的工单草稿工具。",
            "finalize_support_response": "执行最终结果校验器，检查证据、风险和路由前置条件。",
        }.get(tool_name, "执行模型选择的工具。")

    @staticmethod
    def _reindex_trace(trace: list[dict[str, Any]]) -> list[ReactTraceStep]:
        result: list[ReactTraceStep] = []
        for index, item in enumerate(trace, start=1):
            step = ReactTraceStep.model_validate(item)
            step.index = index
            result.append(step)
        return result
