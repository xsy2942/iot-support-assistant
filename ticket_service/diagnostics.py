from __future__ import annotations

from .models import DiagnosticFinding, DiagnosticResult, Priority, Route, TelemetrySample, TicketCreate


def analyze_telemetry(sample: TelemetrySample) -> DiagnosticResult:
    findings: list[DiagnosticFinding] = []

    if sample.customer_risk_signal:
        findings.append(
            DiagnosticFinding(
                category="safety_risk",
                severity="critical",
                evidence=f"customer_risk_signal={sample.customer_risk_signal}",
                action="Stop remote operations and escalate to human support with field logs.",
            )
        )

    if not sample.online or sample.heartbeat_age_sec >= 600:
        findings.append(
            DiagnosticFinding(
                category="device_offline",
                severity="critical" if sample.heartbeat_age_sec >= 600 else "major",
                evidence=f"online={sample.online}, heartbeat_age_sec={sample.heartbeat_age_sec}",
                action="Check power, network, SIM balance, firewall policy, and last heartbeat.",
            )
        )

    if not sample.mqtt_connected or sample.error_code in {"E102", "E104"}:
        findings.append(
            DiagnosticFinding(
                category="mqtt_timeout",
                severity="major",
                evidence=f"mqtt_connected={sample.mqtt_connected}, error_code={sample.error_code or 'none'}",
                action="Verify broker host, port, TLS certificate, device credentials, and weak-network logs.",
            )
        )

    if sample.last_upgrade_status == "failed" or sample.error_code in {"E201", "E203", "E206"}:
        findings.append(
            DiagnosticFinding(
                category="firmware_upgrade_failed",
                severity="critical",
                evidence=f"last_upgrade_status={sample.last_upgrade_status}, error_code={sample.error_code or 'none'}",
                action="Collect upgrade logs and avoid repeated upgrade attempts before human review.",
            )
        )

    if sample.temperature_c >= 55 or sample.humidity_percent >= 85 or sample.error_code in {"E301", "E302", "E303"}:
        findings.append(
            DiagnosticFinding(
                category="sensor_sampling_abnormal",
                severity="major",
                evidence=f"temperature_c={sample.temperature_c}, humidity_percent={sample.humidity_percent}",
                action="Check probe wiring, calibration parameters, sampling period, and installation environment.",
            )
        )

    if sample.voltage_v >= 250 or sample.error_code == "E304":
        findings.append(
            DiagnosticFinding(
                category="power_sampling_risk",
                severity="critical",
                evidence=f"voltage_v={sample.voltage_v}, error_code={sample.error_code or 'none'}",
                action="Check phase sequence, transformer direction, ratio settings, and on-site electrical safety.",
            )
        )

    if sample.rssi_dbm <= -90:
        findings.append(
            DiagnosticFinding(
                category="weak_signal",
                severity="minor",
                evidence=f"rssi_dbm={sample.rssi_dbm}",
                action="Move antenna, check carrier signal, or switch to wired network where possible.",
            )
        )

    if not findings:
        findings.append(
            DiagnosticFinding(
                category="normal",
                severity="info",
                evidence="No major abnormal telemetry threshold was triggered.",
                action="Continue monitoring for two heartbeat cycles.",
            )
        )

    primary = _primary_finding(findings)
    priority = _priority(findings)
    route = _route(findings, priority)
    confidence_score = _confidence(findings, sample)
    summary = _summary(sample, primary)

    ticket_payload = None
    if route in {Route.review, Route.handoff}:
        ticket_payload = TicketCreate(
            question=f"Telemetry diagnosis for {sample.device_model} {sample.device_id}",
            device_model=sample.device_model,
            firmware_version=sample.firmware_version,
            error_code=sample.error_code or None,
            category=primary.category,
            priority=priority,
            summary=summary,
            retrieved_sources=[sample.sample_id],
            suggested_action=primary.action,
        )

    return DiagnosticResult(
        sample_id=sample.sample_id,
        device_id=sample.device_id,
        category=primary.category,
        priority=priority,
        route=route,
        confidence_score=confidence_score,
        findings=findings,
        ticket_payload=ticket_payload,
    )


def _primary_finding(findings: list[DiagnosticFinding]) -> DiagnosticFinding:
    severity_order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
    return sorted(findings, key=lambda finding: severity_order[finding.severity])[0]


def _priority(findings: list[DiagnosticFinding]) -> Priority:
    severities = {finding.severity for finding in findings}
    if "critical" in severities:
        return Priority.p1
    if "major" in severities:
        return Priority.p2
    return Priority.p3


def _route(findings: list[DiagnosticFinding], priority: Priority) -> Route:
    categories = {finding.category for finding in findings}
    if priority == Priority.p1 or "safety_risk" in categories:
        return Route.handoff
    if priority == Priority.p2:
        return Route.review
    return Route.direct_answer


def _confidence(findings: list[DiagnosticFinding], sample: TelemetrySample) -> float:
    score = 0.55 + min(0.35, 0.08 * len(findings))
    if sample.error_code:
        score += 0.07
    if sample.customer_risk_signal:
        score += 0.05
    return min(0.99, round(score, 2))


def _summary(sample: TelemetrySample, primary: DiagnosticFinding) -> str:
    return (
        f"{sample.device_model} {sample.device_id} triggered {primary.category}; "
        f"error_code={sample.error_code or 'none'}, heartbeat_age_sec={sample.heartbeat_age_sec}, "
        f"mqtt_connected={sample.mqtt_connected}."
    )
