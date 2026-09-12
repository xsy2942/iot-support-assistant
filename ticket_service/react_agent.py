from __future__ import annotations

from dataclasses import dataclass, field

from .knowledge_base import KnowledgeBase, KnowledgeHit
from .models import (
    AgentEvidence,
    AgentRequest,
    AgentResponse,
    AgentRoute,
    AgentStatus,
    AgentStep,
    Priority,
    ReactTraceStep,
    TicketCreate,
    TroubleshootingRequest,
    TroubleshootingResult,
)
from .troubleshooting import HIGH_RISK_WORDS, guide_troubleshooting


@dataclass
class ReActState:
    risk_signal: str | None = None
    memory_facts: dict[str, str] = field(default_factory=dict)
    troubleshooting: TroubleshootingResult | None = None
    evidence_hits: list[KnowledgeHit] = field(default_factory=list)
    ticket_payload: TicketCreate | None = None
    final_response: AgentResponse | None = None
    used_actions: set[str] = field(default_factory=set)


class ReActSupportAgent:
    """Dynamic ReAct-style agent that chooses the next tool from observations."""

    def __init__(self, knowledge_base: KnowledgeBase | None = None) -> None:
        self.knowledge_base = knowledge_base or KnowledgeBase()

    def respond(self, request: AgentRequest) -> AgentResponse:
        state = ReActState(risk_signal=self._risk_signal(request), memory_facts=self._memory_facts(request))
        trace: list[ReactTraceStep] = []

        for step_index in range(1, request.max_steps + 1):
            action, reason = self._select_action(request, state)
            observation = self._run_action(action, request, state)
            next_decision = self._next_decision(action, state)
            trace.append(
                ReactTraceStep(
                    index=step_index,
                    reasoning_summary=reason,
                    action=action,
                    action_input=self._action_input(action, request),
                    observation=observation,
                    next_decision=next_decision,
                )
            )
            state.used_actions.add(action)
            if state.final_response is not None:
                state.final_response.react_trace = trace
                state.final_response.plan = self._plan_from_trace(trace)
                return state.final_response

        fallback = self._unknown_response(request, state)
        fallback.react_trace = trace
        fallback.plan = self._plan_from_trace(trace)
        return fallback

    def _select_action(self, request: AgentRequest, state: ReActState) -> tuple[str, str]:
        if "memory.read" not in state.used_actions:
            return "memory.read", "先读取当前会话已经沉淀的设备事实，避免重复追问。"
        if state.risk_signal and "ticket.draft" not in state.used_actions:
            return "ticket.draft", f"命中高风险信号 {state.risk_signal}，优先生成转人工工单草稿。"
        if state.ticket_payload is not None:
            return "final.handoff", "已经生成转人工工单草稿，本轮不再追问，直接交给人工复核。"
        if state.troubleshooting is None:
            return "troubleshooting.guide", "根据当前事实检查是否缺少设备型号、网络状态、错误码等关键字段。"
        if state.troubleshooting.missing_fields and not self._has_enough_specificity(request) and "final.clarify" not in state.used_actions:
            return "final.clarify", "观察到信息不足，先追问关键字段，不进入强答。"
        if "knowledge.search" not in state.used_actions:
            return "knowledge.search", "问题具备基本上下文，调用本地知识库检索可引用证据。"
        if state.evidence_hits and state.evidence_hits[0].score >= 0.12:
            return "final.answer", "观察到知识库命中可靠证据，生成带引用的回答。"
        if "ticket.draft" not in state.used_actions:
            return "ticket.draft", "知识库证据不足，准备人工复核工单。"
        return "final.handoff", "已经生成工单草稿，返回转人工结论。"

    def _run_action(self, action: str, request: AgentRequest, state: ReActState) -> dict[str, object]:
        if action == "memory.read":
            return {"memory_facts": state.memory_facts, "fact_count": len(state.memory_facts)}
        if action == "troubleshooting.guide":
            state.troubleshooting = guide_troubleshooting(self._to_troubleshooting_request(request, state.risk_signal))
            return {
                "issue_type": state.troubleshooting.issue_type,
                "missing_fields": state.troubleshooting.missing_fields,
                "route": state.troubleshooting.route.value,
            }
        if action == "knowledge.search":
            state.evidence_hits = self.knowledge_base.search(
                request.question,
                top_k=request.top_k,
                device_model=request.device_model,
                error_code=request.error_code,
                issue_type=request.issue_type,
            )
            return {
                "hit_count": len(state.evidence_hits),
                "top_score": state.evidence_hits[0].score if state.evidence_hits else 0,
                "top_sources": [hit.chunk_id for hit in state.evidence_hits[: request.top_k]],
            }
        if action == "ticket.draft":
            state.ticket_payload = self._ticket_payload(
                request=request,
                category="高风险人工介入" if state.risk_signal else self._issue_type(state),
                priority=Priority.p1 if state.risk_signal else Priority.p2,
                sources=[hit.chunk_id for hit in state.evidence_hits],
                action="涉及高风险或证据不足，建议转人工并保留设备日志。",
            )
            return {
                "priority": state.ticket_payload.priority.value,
                "category": state.ticket_payload.category,
                "retrieved_sources": state.ticket_payload.retrieved_sources,
            }
        if action == "final.clarify":
            state.final_response = self._clarify_response(request, state)
            return {"route": state.final_response.route.value, "status": state.final_response.status.value}
        if action == "final.answer":
            state.final_response = self._answer_response(request, state)
            return {"route": state.final_response.route.value, "status": state.final_response.status.value}
        if action == "final.handoff":
            state.final_response = self._handoff_response(request, state)
            return {"route": state.final_response.route.value, "status": state.final_response.status.value}
        raise ValueError(f"Unknown ReAct action: {action}")

    @staticmethod
    def _next_decision(action: str, state: ReActState) -> str:
        if action == "memory.read":
            return "继续检查信息完整度。"
        if action == "troubleshooting.guide" and state.troubleshooting and state.troubleshooting.missing_fields:
            return "若问题仍不具体则追问，否则尝试检索知识库。"
        if action == "knowledge.search" and state.evidence_hits:
            return "根据证据置信度决定回答或转人工。"
        if action == "ticket.draft":
            return "进入转人工结论。"
        return "结束本轮 ReAct 执行。"

    @staticmethod
    def _action_input(action: str, request: AgentRequest) -> dict[str, object]:
        if action == "knowledge.search":
            return {
                "query": request.question,
                "top_k": request.top_k,
                "device_model": request.device_model or "",
                "error_code": request.error_code or "",
                "issue_type": request.issue_type or "",
            }
        if action == "memory.read":
            return {"session_id": request.session_id or "", "attachment_count": len(request.attachments)}
        if action == "troubleshooting.guide":
            return {"question": request.question, "device_model": request.device_model or "", "error_code": request.error_code or ""}
        if action == "ticket.draft":
            return {
                "question": request.question,
                "device_model": request.device_model or "",
                "error_code": request.error_code or "",
                "attachment_count": len(request.attachments),
            }
        return {}

    @staticmethod
    def _plan_from_trace(trace: list[ReactTraceStep]) -> list[AgentStep]:
        return [
            AgentStep(
                index=step.index,
                name=step.action,
                tool=step.action,
                reason=step.reasoning_summary,
                status="done",
            )
            for step in trace
        ]

    def _clarify_response(self, request: AgentRequest, state: ReActState) -> AgentResponse:
        assert state.troubleshooting is not None
        questions = state.troubleshooting.follow_up_questions
        answer = "当前信息还不完整，建议先向客户确认：" + "；".join(question.question for question in questions)
        if request.attachments:
            answer += "。客户图片已作为附件保留，可在人工复核时查看。"
        return AgentResponse(
            session_id=request.session_id,
            route=AgentRoute.clarify,
            status=AgentStatus.incomplete,
            answer=answer,
            confidence_score=state.troubleshooting.confidence_score,
            plan=[],
            evidence=self._evidence(state.evidence_hits[:1]),
            follow_up_questions=questions,
            memory_facts=state.memory_facts,
        )

    def _answer_response(self, request: AgentRequest, state: ReActState) -> AgentResponse:
        primary = state.evidence_hits[0]
        related = "、".join(hit.chunk_id for hit in state.evidence_hits[: request.top_k])
        answer = self._customer_reply(request, primary, related)
        if request.attachments:
            answer += " 客户图片已随本次问题保留，可作为后续复核凭证。"
        return AgentResponse(
            session_id=request.session_id,
            route=AgentRoute.rag_answer,
            status=AgentStatus.complete if primary.score >= 0.25 else AgentStatus.partial,
            answer=answer,
            confidence_score=min(0.95, round(primary.score + 0.3, 2)),
            plan=[],
            evidence=self._evidence(state.evidence_hits),
            memory_facts=state.memory_facts,
        )

    def _handoff_response(self, request: AgentRequest, state: ReActState) -> AgentResponse:
        if state.ticket_payload is None:
            state.ticket_payload = self._ticket_payload(
                request=request,
                category=self._issue_type(state),
                priority=Priority.p2,
                sources=[hit.chunk_id for hit in state.evidence_hits],
                action="证据不足，建议人工复核。",
            )
        return AgentResponse(
            session_id=request.session_id,
            route=AgentRoute.handoff,
            status=AgentStatus.partial if state.risk_signal else AgentStatus.unknown,
            answer="该问题涉及高风险或证据不足，不建议直接强答，已生成转人工工单草稿。",
            confidence_score=0.86 if state.risk_signal else 0.35,
            plan=[],
            evidence=self._evidence(state.evidence_hits),
            follow_up_questions=state.troubleshooting.follow_up_questions if state.troubleshooting else [],
            memory_facts=state.memory_facts,
            ticket_payload=state.ticket_payload,
        )

    def _unknown_response(self, request: AgentRequest, state: ReActState) -> AgentResponse:
        return AgentResponse(
            session_id=request.session_id,
            route=AgentRoute.handoff,
            status=AgentStatus.unknown,
            answer="本轮没有获得足够可靠证据，建议转人工复核。",
            confidence_score=0.3,
            plan=[],
            evidence=self._evidence(state.evidence_hits),
            memory_facts=state.memory_facts,
            ticket_payload=state.ticket_payload,
        )

    @staticmethod
    def _risk_signal(request: AgentRequest) -> str | None:
        if request.risk_signal:
            return request.risk_signal
        for word in HIGH_RISK_WORDS:
            if word in request.question:
                return word
        return None

    @staticmethod
    def _has_enough_specificity(request: AgentRequest) -> bool:
        return bool(request.device_model or request.error_code) or any(
            token in request.question.upper() for token in ("E101", "E102", "E104", "E201", "E203", "GW-", "TH-", "AQ-", "VB-", "PM-")
        )

    @staticmethod
    def _to_troubleshooting_request(request: AgentRequest, risk_signal: str | None) -> TroubleshootingRequest:
        return TroubleshootingRequest(
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
            risk_signal=risk_signal or request.risk_signal,
        )

    @staticmethod
    def _memory_facts(request: AgentRequest) -> dict[str, str]:
        fields = (
            "issue_type",
            "device_model",
            "firmware_version",
            "error_code",
            "online_status",
            "indicator_light",
            "network_type",
            "heartbeat_age_sec",
            "mqtt_connected",
            "last_upgrade_status",
            "risk_signal",
        )
        return {
            field: str(getattr(request, field))
            for field in fields
            if getattr(request, field) is not None and getattr(request, field) != ""
        }

    @staticmethod
    def _issue_type(state: ReActState) -> str:
        if state.troubleshooting:
            return state.troubleshooting.issue_type
        if state.evidence_hits:
            return state.evidence_hits[0].issue_type
        return "agent_handoff"

    @staticmethod
    def _ticket_payload(
        request: AgentRequest,
        category: str,
        priority: Priority,
        sources: list[str],
        action: str,
    ) -> TicketCreate:
        return TicketCreate(
            question=request.question,
            device_model=request.device_model,
            firmware_version=request.firmware_version,
            error_code=request.error_code,
            category=category,
            priority=priority,
            summary=(
                f"{request.device_model or '未知设备'} 由 ReAct Agent 触发转人工；"
                f"错误码={request.error_code or '未知'}，问题={request.question[:80]}。"
            ),
            retrieved_sources=sources,
            suggested_action=action,
            attachments=request.attachments,
        )

    @staticmethod
    def _evidence(hits: list[KnowledgeHit]) -> list[AgentEvidence]:
        return [
            AgentEvidence(
                source_id=hit.chunk_id,
                source_type=hit.source_type,
                title=hit.title,
                score=hit.score,
                quote=hit.content[:220],
                metadata={
                    "parent_id": hit.parent_id,
                    "child_id": hit.child_id,
                    "sibling_count": str(hit.sibling_count),
                    "route_path": f"{hit.parent_id} -> {hit.child_id}",
                    "product_line": hit.product_line,
                    "device_model": hit.device_model,
                    "error_code": hit.error_code,
                    "issue_type": hit.issue_type,
                },
            )
            for hit in hits
        ]

    @staticmethod
    def _customer_reply(request: AgentRequest, primary: KnowledgeHit, related: str) -> str:
        device = request.device_model or primary.device_model or "该设备"
        error_code = request.error_code or primary.error_code
        issue_type = request.issue_type or primary.issue_type or "当前问题"
        steps = ReActSupportAgent._extract_steps(primary.content)
        if not steps:
            steps = [
                "确认设备型号、固件版本、错误码和最近一次故障时间。",
                "检查供电、网络状态、平台在线状态和最近心跳时间。",
                "保留设备日志和现场现象，若仍无法恢复则转人工复核。",
            ]

        lines = [f"建议您按照以下步骤排查 {device} 的{issue_type}："]
        for index, step in enumerate(steps[:4], start=1):
            lines.append(f"{index}. {step}")
        if error_code:
            lines.append(f"{len(lines)}. 同步核对平台日志中是否持续出现错误码 {error_code}。")
        lines.append(f"参考来源：{related}。")
        lines.append("如果现场情况与资料不一致，或涉及投诉、赔偿、安全风险，请转人工复核。")
        return "\n".join(lines)

    @staticmethod
    def _extract_steps(content: str) -> list[str]:
        text = content.strip().replace("\n", " ")
        if "MQTT" in text or "Broker" in text:
            return [
                "核对 Broker 域名、端口和 TLS 证书是否与平台配置一致。",
                "检查设备三元组、认证信息和防火墙策略是否被修改。",
                "查看设备日志中的错误码记录和最近心跳时间。",
                "处理后观察两个心跳周期，确认数据是否恢复。",
            ]
        if "设备离线" in text or "心跳" in text:
            return [
                "确认设备供电、网线或 SIM 卡网络是否正常。",
                "检查平台最近心跳时间，判断是持续离线还是间歇离线。",
                "核对 MQTT Broker 地址和防火墙放行策略。",
                "重启设备后继续观察两个心跳周期。",
            ]
        if "固件" in text or "升级" in text:
            return [
                "确认设备型号、当前固件版本和目标固件版本是否匹配。",
                "检查升级包校验值、网络稳定性和剩余存储空间。",
                "导出升级日志，避免连续反复下发升级任务。",
                "升级失败仍未恢复时转人工复核。",
            ]
        if "传感器" in text or "采样" in text:
            return [
                "检查传感器接线、探头安装位置和采样周期配置。",
                "核对校准参数、阈值模板和现场环境变化。",
                "对比历史正常数据，确认异常是否持续出现。",
                "异常持续时保留采样日志并转人工复核。",
            ]
        marker_candidates = ("标准步骤：", "解决方案：", "建议先")
        selected = text
        for marker in marker_candidates:
            if marker in text:
                selected = text.split(marker, 1)[1]
                break
        selected = selected.split("建议动作：", 1)[0]
        selected = selected.split("若 10 分钟", 1)[0]
        selected = selected.split("处理后", 1)[0]
        parts = [
            part.strip(" ，。；;")
            for part in selected.replace("并", "、").replace("和", "、").split("、")
            if part.strip(" ，。；;")
        ]
        return [part if part.endswith("。") else f"{part}。" for part in parts if len(part) >= 2]
