from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def test_ticket_feedback_report_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("TICKET_DB_PATH", str(tmp_path / "tickets.sqlite3"))

    import ticket_service.main as main

    importlib.reload(main)
    client = TestClient(main.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "IoT Support Assistant" in dashboard.text

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
    monkeypatch.setenv("TICKET_DB_PATH", str(tmp_path / "tickets.sqlite3"))

    import ticket_service.main as main

    importlib.reload(main)
    client = TestClient(main.app)

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
