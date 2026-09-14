from __future__ import annotations

import json
from types import SimpleNamespace

from ticket_service.langgraph_agent import LangGraphSupportAgent
from ticket_service.llm_provider import AgentModelSettings, OpenAIChatToolModel
from ticket_service.models import AgentRequest


def tool_completion(name: str, arguments: dict[str, object], call_id: str) -> SimpleNamespace:
    function = SimpleNamespace(name=name, arguments=json.dumps(arguments, ensure_ascii=False))
    tool_call = SimpleNamespace(id=call_id, function=function)
    message = SimpleNamespace(content=None, tool_calls=[tool_call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeCompletions:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


def make_agent(responses: list[SimpleNamespace]) -> tuple[LangGraphSupportAgent, FakeClient]:
    client = FakeClient(responses)
    settings = AgentModelSettings(
        provider="deepseek",
        api_key="test-key",
        base_url="https://example.invalid/v1",
        model="test-tool-model",
    )
    model = OpenAIChatToolModel(settings, client=client)
    return LangGraphSupportAgent(model=model), client


def test_langgraph_uses_llm_selected_search_and_finalizer_tools():
    agent, client = make_agent(
        [
            tool_completion(
                "search_iot_knowledge",
                {
                    "query": "GW-200 E104 MQTT 连接超时",
                    "top_k": 3,
                    "device_model": "GW-200",
                    "error_code": "E104",
                },
                "call-search",
            ),
            tool_completion(
                "finalize_support_response",
                {
                    "route": "rag_answer",
                    "answer": "建议先核对 Broker 地址、端口与 TLS 证书，再检查设备认证和最近心跳。",
                    "confidence_score": 0.86,
                    "source_ids": [],
                },
                "call-final",
            ),
        ]
    )

    response = agent.respond(
        AgentRequest(
            question="GW-200 报 E104，MQTT 连接超时应该怎么排查？",
            device_model="GW-200",
            error_code="E104",
            online_status="离线",
            mqtt_connected=False,
        )
    )

    assert response.runtime == "langgraph-tool-calling"
    assert response.model_provider == "deepseek"
    assert response.model_name == "test-tool-model"
    assert response.route.value == "rag_answer"
    assert response.evidence
    assert "参考来源" in response.answer
    assert [step.action for step in response.react_trace] == [
        "llm.plan",
        "knowledge.search",
        "llm.plan",
        "final.answer",
    ]
    assert len(client.completions.calls) == 2
    assert {tool["function"]["name"] for tool in client.completions.calls[0]["tools"]} >= {
        "search_iot_knowledge",
        "finalize_support_response",
    }


def test_langgraph_verifier_rejects_high_risk_direct_answer():
    agent, _ = make_agent(
        [
            tool_completion(
                "finalize_support_response",
                {
                    "route": "rag_answer",
                    "answer": "可以继续远程操作。",
                    "confidence_score": 0.9,
                    "source_ids": [],
                },
                "call-invalid-final",
            ),
            tool_completion(
                "draft_support_ticket",
                {
                    "category": "设备安全风险",
                    "priority": "P2",
                    "summary": "GW-200 现场冒烟并伴随数据丢失，需要立即人工处理。",
                    "suggested_action": "停止远程操作，保留日志并联系二线工程师。",
                },
                "call-ticket",
            ),
            tool_completion(
                "finalize_support_response",
                {
                    "route": "handoff",
                    "answer": "请立即停止设备远程操作并保持现场安全，工单已提交人工复核。",
                    "confidence_score": 0.92,
                    "source_ids": [],
                },
                "call-handoff",
            ),
        ]
    )

    response = agent.respond(
        AgentRequest(
            question="GW-200 现场冒烟并且数据丢失，还能继续远程重启吗？",
            device_model="GW-200",
            max_steps=4,
        )
    )

    assert response.runtime == "langgraph-tool-calling"
    assert response.route.value == "handoff"
    assert response.ticket_payload is not None
    assert response.ticket_payload.priority.value == "P1"
    invalid_step = next(step for step in response.react_trace if step.action == "final.answer")
    assert invalid_step.observation["ok"] is False
    assert "High-risk" in invalid_step.observation["error"]
