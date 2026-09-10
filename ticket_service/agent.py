from __future__ import annotations

from .knowledge_base import KnowledgeBase, KnowledgeHit
from .models import (
    AgentEvidence,
    AgentRequest,
    AgentResponse,
    AgentRoute,
    AgentStatus,
    AgentStep,
    Priority,
    TicketCreate,
    TroubleshootingRequest,
)
from .troubleshooting import HIGH_RISK_WORDS, guide_troubleshooting


class SupportAgent:
    """Python-native IoT support agent: route, plan, call tools, then verify evidence."""

    def __init__(self, knowledge_base: KnowledgeBase | None = None) -> None:
        self.knowledge_base = knowledge_base or KnowledgeBase()

    def respond(self, request: AgentRequest) -> AgentResponse:
        risk_signal = self._risk_signal(request)
        troubleshooting = guide_troubleshooting(self._to_troubleshooting_request(request, risk_signal))
        evidence_hits = self.knowledge_base.search(request.question, top_k=request.top_k)
        plan = self._plan(request, risk_signal, troubleshooting.missing_fields, evidence_hits)

        if risk_signal:
            ticket_payload = self._ticket_payload(
                request=request,
                category="高风险人工介入",
                priority=Priority.p1,
                sources=[hit.chunk_id for hit in evidence_hits],
                action="涉及投诉、安全事故、赔偿或数据丢失，建议转人工并保留现场证据。",
            )
            return AgentResponse(
                route=AgentRoute.handoff,
                status=AgentStatus.partial,
                answer="该问题包含高风险信号，系统不直接给出最终处理结论。建议转人工，并收集现场照片、设备日志、平台操作记录和客户诉求。",
                confidence_score=0.86,
                plan=self._finish_plan(plan, "handoff"),
                evidence=self._evidence(evidence_hits),
                follow_up_questions=troubleshooting.follow_up_questions,
                ticket_payload=ticket_payload,
            )

        if self._needs_clarification(request, troubleshooting.missing_fields, evidence_hits):
            questions = troubleshooting.follow_up_questions
            answer = "当前描述还不够完整，先补齐关键信息再进入知识库问答或规则诊断。请优先确认：" + "；".join(
                question.question for question in questions
            )
            return AgentResponse(
                route=AgentRoute.clarify,
                status=AgentStatus.incomplete,
                answer=answer,
                confidence_score=troubleshooting.confidence_score,
                plan=self._finish_plan(plan, "clarify"),
                evidence=self._evidence(evidence_hits[:1]),
                follow_up_questions=questions,
            )

        if evidence_hits and evidence_hits[0].score >= 0.12:
            return AgentResponse(
                route=AgentRoute.rag_answer,
                status=AgentStatus.complete if evidence_hits[0].score >= 0.25 else AgentStatus.partial,
                answer=self._build_rag_answer(request.question, evidence_hits),
                confidence_score=min(0.95, round(evidence_hits[0].score + 0.3, 2)),
                plan=self._finish_plan(plan, "rag_answer"),
                evidence=self._evidence(evidence_hits),
                follow_up_questions=[],
            )

        ticket_payload = self._ticket_payload(
            request=request,
            category=troubleshooting.issue_type,
            priority=Priority.p2,
            sources=[],
            action="知识库未命中可靠资料，建议生成工单由人工复核。",
        )
        return AgentResponse(
            route=AgentRoute.handoff,
            status=AgentStatus.unknown,
            answer="知识库没有命中足够可靠的资料，系统不强行编造答案，建议创建人工复核工单。",
            confidence_score=0.35,
            plan=self._finish_plan(plan, "unknown"),
            evidence=[],
            follow_up_questions=troubleshooting.follow_up_questions,
            ticket_payload=ticket_payload,
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
    def _risk_signal(request: AgentRequest) -> str | None:
        if request.risk_signal:
            return request.risk_signal
        for word in HIGH_RISK_WORDS:
            if word in request.question:
                return word
        return None

    @staticmethod
    def _needs_clarification(request: AgentRequest, missing_fields: list[str], hits: list[KnowledgeHit]) -> bool:
        if not missing_fields:
            return False
        enough_specificity = bool(request.device_model or request.error_code) or any(
            token in request.question.upper() for token in ("E101", "E102", "E104", "E201", "E203", "GW-", "TH-")
        )
        strong_evidence = bool(hits and hits[0].score >= 0.18)
        return not (enough_specificity and strong_evidence)

    @staticmethod
    def _plan(
        request: AgentRequest,
        risk_signal: str | None,
        missing_fields: list[str],
        hits: list[KnowledgeHit],
    ) -> list[AgentStep]:
        steps = [
            AgentStep(index=1, name="Fast Router", tool="router", reason="识别问题是否需要追问、检索或转人工。"),
            AgentStep(index=2, name="Structured Planner", tool="planner", reason="把用户问题拆成可执行步骤。"),
            AgentStep(index=3, name="Knowledge Search", tool="local_hybrid_retriever", reason="在 IoT 知识分块中做向量+关键词混合检索。"),
            AgentStep(index=4, name="Capability Executor", tool="tool_registry", reason="调用排障树、知识库检索和工单草稿能力。"),
            AgentStep(index=5, name="Verifier", tool="evidence_verifier", reason="检查证据、风险和输出状态。"),
        ]
        if risk_signal:
            steps[0].reason = f"命中高风险词：{risk_signal}。"
        elif missing_fields:
            steps[0].reason = f"识别到缺失字段：{', '.join(missing_fields[:3])}。"
        elif hits:
            steps[2].reason = f"最高命中分数：{hits[0].score:.2f}。"
        return steps

    @staticmethod
    def _finish_plan(plan: list[AgentStep], final_tool: str) -> list[AgentStep]:
        return [step.model_copy(update={"status": "done" if step.tool != final_tool else "verified"}) for step in plan]

    @staticmethod
    def _build_rag_answer(question: str, hits: list[KnowledgeHit]) -> str:
        primary = hits[0]
        action = primary.content.strip().replace("\n", " ")
        related = "、".join(hit.chunk_id for hit in hits[:3])
        return (
            f"根据本地 IoT 售后知识库，问题“{question}”最相关的资料是《{primary.title}》。"
            f"建议处理：{action} "
            f"引用来源：{related}。如果现场现象与引用资料不一致，或客户涉及投诉/赔偿/安全风险，应转人工复核。"
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
                    "product_line": hit.product_line,
                    "device_model": hit.device_model,
                    "error_code": hit.error_code,
                    "issue_type": hit.issue_type,
                },
            )
            for hit in hits
        ]

    @staticmethod
    def _ticket_payload(
        request: AgentRequest,
        category: str,
        priority: Priority,
        sources: list[str],
        action: str,
    ) -> TicketCreate:
        summary = (
            f"{request.device_model or '未知设备'} 提交 Agent 转人工；"
            f"错误码={request.error_code or '未知'}，问题={request.question[:80]}。"
        )
        return TicketCreate(
            question=request.question,
            device_model=request.device_model,
            firmware_version=request.firmware_version,
            error_code=request.error_code,
            category=category,
            priority=priority,
            summary=summary,
            retrieved_sources=sources,
            suggested_action=action,
        )
