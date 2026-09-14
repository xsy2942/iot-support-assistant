from __future__ import annotations

import asyncio
import importlib

from fastapi.testclient import TestClient


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("TICKET_DB_PATH", str(tmp_path / "tickets.sqlite3"))
    monkeypatch.setenv("TICKET_DB_URL", "")
    monkeypatch.setenv("TROUBLESHOOTING_REDIS_URL", "")
    monkeypatch.setenv("AGENT_MEMORY_REDIS_URL", "")
    monkeypatch.setenv("AGENT_MODE", "deterministic")

    import ticket_service.main as main

    importlib.reload(main)
    return TestClient(main.app)


def test_ticket_feedback_report_flow(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["database"] == "sqlite"
    assert health.json()["session_memory"] == "stateless"

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "IoT Support Agent" in dashboard.text

    ticket_payload = {
        "question": "GW-200 报 E104 且心跳丢失，客户已经重启设备。",
        "device_model": "GW-200",
        "firmware_version": "v2.0.1",
        "error_code": "E104",
        "category": "设备离线",
        "priority": "P1",
        "summary": "GW-200 出现 E104 心跳超时，现场已重启，建议人工检查网络和日志。",
        "retrieved_sources": ["ERR-004", "FAQ-001"],
        "suggested_action": "建议转人工并收集最近 30 分钟日志",
    }
    created = client.post("/tickets/create", json=ticket_payload)
    assert created.status_code == 200
    ticket_id = created.json()["ticket_id"]

    tickets = client.get("/tickets")
    assert tickets.status_code == 200
    assert len(tickets.json()) == 1

    updated = client.post(f"/tickets/{ticket_id}/status", json={"status": "reviewing"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "reviewing"

    reviewing = client.get("/tickets", params={"status": "reviewing"})
    assert reviewing.status_code == 200
    assert [ticket["ticket_id"] for ticket in reviewing.json()] == [ticket_id]

    feedback = client.post(
        "/feedback",
        json={
            "question": ticket_payload["question"],
            "answer": "建议检查 Broker、SIM 卡与心跳日志。",
            "useful": True,
            "ticket_id": ticket_id,
            "comment": "摘要可用",
            "retrieved_sources": ["ERR-004"],
        },
    )
    assert feedback.status_code == 200

    report = client.get("/eval/report")
    assert report.status_code == 200
    assert report.json()["ticket_count"] == 1
    assert report.json()["feedback_count"] == 1
    assert report.json()["useful_feedback_rate"] == 1.0


def test_diagnostics_can_create_ticket(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    sample = {
        "sample_id": "TEL-TEST-001",
        "timestamp": "2026-04-01T10:00:00",
        "device_id": "DEV-GW200-001",
        "product_line": "gateway",
        "device_model": "GW-200",
        "firmware_version": "v2.0.1",
        "online": False,
        "mqtt_connected": False,
        "heartbeat_age_sec": 900,
        "rssi_dbm": -96,
        "battery_percent": 72,
        "temperature_c": 28.5,
        "humidity_percent": 55.0,
        "vibration_mm_s": 1.2,
        "voltage_v": 229.0,
        "error_code": "E104",
        "last_upgrade_status": "idle",
        "customer_risk_signal": None,
    }

    diagnosis = client.post("/diagnostics/analyze", json=sample)
    assert diagnosis.status_code == 200
    body = diagnosis.json()
    assert body["category"] == "device_offline"
    assert body["priority"] == "P1"
    assert body["route"] == "handoff"
    assert body["ticket_payload"] is not None

    ticket = client.post("/diagnostics/create-ticket", json=sample)
    assert ticket.status_code == 200
    assert ticket.json()["category"] == "device_offline"


def test_troubleshooting_asks_follow_up_for_incomplete_question(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/troubleshooting/next",
        json={
            "question": "设备连不上平台了，现场人员也说不清楚具体原因。",
            "issue_type": "设备离线",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["issue_type"] == "设备离线"
    assert body["route"] == "direct_answer"
    assert "device_model" in body["missing_fields"]
    assert len(body["follow_up_questions"]) == 3
    assert body["ticket_payload"] is None


def test_troubleshooting_can_escalate_and_create_ticket(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    payload = {
        "question": "GW-200 固件升级失败，客户投诉现场数据丢失。",
        "issue_type": "固件升级失败",
        "device_model": "GW-200",
        "error_code": "E203",
        "network_type": "4G",
        "last_upgrade_status": "failed",
        "tried_steps": ["重启设备", "重新下发升级任务"],
    }

    result = client.post("/troubleshooting/next", json=payload)
    assert result.status_code == 200
    body = result.json()
    assert body["route"] == "handoff"
    assert body["priority"] == "P1"
    assert body["ticket_payload"] is not None

    ticket = client.post("/troubleshooting/create-ticket", json=payload)
    assert ticket.status_code == 200
    assert ticket.json()["category"] == "固件升级失败"


def test_agent_clarifies_incomplete_question(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.post("/agent/respond", json={"question": "设备连不上平台了，现场也说不清楚。"})

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "clarify"
    assert body["status"] == "INCOMPLETE"
    assert body["follow_up_questions"]
    assert "设备型号" in body["answer"]


def test_agent_answers_with_local_knowledge_evidence(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/agent/respond",
        json={
            "question": "GW-200 报 E104 且 MQTT 连接超时，平台显示心跳 15 分钟没有上报，应该怎么排查？",
            "device_model": "GW-200",
            "error_code": "E104",
            "online_status": "离线",
            "network_type": "4G",
            "mqtt_connected": False,
            "heartbeat_age_sec": 900,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "rag_answer"
    assert body["evidence"]
    assert body["react_trace"][0]["action"] == "memory.read"
    assert "knowledge.search" in {step["action"] for step in body["react_trace"]}
    assert "参考来源" in body["answer"]


def test_agent_replaces_online_status_with_latest_input(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    common = {
        "session_id": "status-change-test",
        "question": "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？",
        "device_model": "GW-200",
        "error_code": "E104",
        "issue_type": "MQTT 连接超时",
        "mqtt_connected": False,
    }

    online = client.post("/agent/respond", json={**common, "online_status": "在线"})
    offline = client.post("/agent/respond", json={**common, "online_status": "离线"})

    assert online.status_code == 200
    assert offline.status_code == 200
    assert "设备当前仍在线" in online.json()["answer"]
    assert "设备当前显示离线" in offline.json()["answer"]
    assert online.json()["answer"] != offline.json()["answer"]
    assert offline.json()["memory_facts"]["online_status"] == "离线"


def test_ticket_can_store_image_attachment_metadata(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    ticket_payload = {
        "question": "客户上传设备面板照片，怀疑网关离线。",
        "device_model": "GW-200",
        "error_code": "E104",
        "category": "设备离线",
        "priority": "P1",
        "summary": "客户上传现场图片，设备疑似离线，建议人工复核。",
        "retrieved_sources": ["image_attachment"],
        "suggested_action": "保留图片和现场日志，转人工复核。",
        "attachments": [
            {
                "filename": "gateway-panel.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 248120,
                "note": "客户上传的设备现场图片或错误截图",
            }
        ],
    }

    created = client.post("/tickets/create", json=ticket_payload)
    assert created.status_code == 200
    assert created.json()["attachments"][0]["filename"] == "gateway-panel.jpg"

    tickets = client.get("/tickets")
    assert tickets.status_code == 200
    assert tickets.json()[0]["attachments"][0]["content_type"] == "image/jpeg"


def test_agent_escalates_high_risk_question(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/agent/respond",
        json={
            "question": "客户要求赔偿停机损失，现场设备冒烟并且历史数据全部丢失。",
            "device_model": "GW-200",
            "error_code": "E104",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "handoff"
    assert body["status"] == "PARTIAL"
    assert body["ticket_payload"] is not None


def test_agent_memory_merges_session_context(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    first = client.post(
        "/agent/respond",
        json={
            "session_id": "memory-test",
            "question": "这台设备连不上平台了。",
            "device_model": "GW-200",
            "online_status": "离线",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/agent/respond",
        json={
            "session_id": "memory-test",
            "question": "刚才那台设备又看到 E104，MQTT 也连不上。",
            "error_code": "E104",
            "mqtt_connected": False,
        },
    )

    assert second.status_code == 200
    body = second.json()
    assert body["session_id"] == "memory-test"
    assert body["memory_facts"]["device_model"] == "GW-200"
    assert body["memory_facts"]["error_code"] == "E104"

    memory = client.get("/agent/memory/memory-test")
    assert memory.status_code == 200
    assert memory.json()["facts"]["device_model"] == "GW-200"
    assert len(memory.json()["turns"]) == 2

    cleared = client.delete("/agent/memory/memory-test")
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] is True

    empty = client.get("/agent/memory/memory-test")
    assert empty.status_code == 200
    assert empty.json()["facts"] == {}


def test_agent_evidence_contains_parent_child_route(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/agent/respond",
        json={
            "question": "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？",
            "device_model": "GW-200",
            "error_code": "E104",
        },
    )

    assert response.status_code == 200
    evidence = response.json()["evidence"]
    assert evidence
    assert "parent_id" in evidence[0]["metadata"]
    assert "route_path" in evidence[0]["metadata"]


def test_agent_sse_stream_returns_result(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.get(
        "/agent/respond/stream",
        params={"question": "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？", "device_model": "GW-200", "error_code": "E104"},
    )

    assert response.status_code == 200
    assert "event: step" in response.text
    assert "event: result" in response.text


def test_mcp_lists_and_calls_agent_tool(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    tools = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert tools.status_code == 200
    assert tools.json()["result"]["tools"][0]["name"] == "agent.respond"

    call = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "knowledge.search",
                "arguments": {"query": "GW-200 E104 MQTT 连接超时", "top_k": 2},
            },
        },
    )

    assert call.status_code == 200
    body = call.json()
    assert body["jsonrpc"] == "2.0"
    assert body["result"]["content"][0]["type"] == "text"
    assert "parent_id" in body["result"]["content"][0]["text"]


def test_official_mcp_server_exposes_tools_and_resources(tmp_path, monkeypatch):
    monkeypatch.setenv("TICKET_DB_PATH", str(tmp_path / "mcp-tickets.sqlite3"))
    monkeypatch.setenv("TICKET_DB_URL", "")
    monkeypatch.setenv("AGENT_MEMORY_REDIS_URL", "")
    monkeypatch.setenv("AGENT_MODE", "deterministic")

    from ticket_service.mcp_server import build_mcp_server

    async def run_check():
        server = build_mcp_server()
        tools = await server.list_tools()
        tool_names = {tool.name for tool in tools}
        assert {"agent_respond", "knowledge_search", "ticket_create"} <= tool_names

        resources = await server.list_resources()
        assert "iot://knowledge/summary" in {str(resource.uri) for resource in resources}

        result = await server.call_tool(
            "agent_respond",
            {
                "question": "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？",
                "device_model": "GW-200",
                "error_code": "E104",
            },
        )
        assert result.structured_content["route"] == "rag_answer"
        assert result.structured_content["evidence"]

    asyncio.run(run_check())
