from __future__ import annotations

from dataclasses import dataclass

from .models import (
    Priority,
    Route,
    TicketCreate,
    TroubleshootingQuestion,
    TroubleshootingRequest,
    TroubleshootingResult,
)


@dataclass(frozen=True)
class TroubleshootingTree:
    issue_type: str
    aliases: tuple[str, ...]
    required_fields: tuple[str, ...]
    follow_up_questions: dict[str, TroubleshootingQuestion]
    default_action: str


TREES = (
    TroubleshootingTree(
        issue_type="设备离线",
        aliases=("离线", "连不上", "无心跳", "心跳丢失", "不在线"),
        required_fields=("device_model", "online_status", "indicator_light", "network_type", "error_code"),
        follow_up_questions={
            "device_model": TroubleshootingQuestion(
                field="device_model",
                question="请确认设备型号，例如 GW-100、GW-200、TH-10。",
                options=["GW-100", "GW-200", "GW-500", "其他"],
            ),
            "online_status": TroubleshootingQuestion(
                field="online_status",
                question="平台上显示设备当前是否在线？",
                options=["在线", "离线", "不确定"],
            ),
            "indicator_light": TroubleshootingQuestion(
                field="indicator_light",
                question="设备指示灯状态是什么？",
                options=["常亮", "闪烁", "不亮", "不确定"],
            ),
            "network_type": TroubleshootingQuestion(
                field="network_type",
                question="设备使用的是哪种网络接入？",
                options=["4G", "以太网", "Wi-Fi", "不确定"],
            ),
            "error_code": TroubleshootingQuestion(
                field="error_code",
                question="平台或设备屏幕是否显示错误码？没有则填“无”。",
                options=["E102", "E104", "E107", "无"],
            ),
        },
        default_action="优先检查供电、网络链路、SIM 卡余额、防火墙策略和最近心跳时间。",
    ),
    TroubleshootingTree(
        issue_type="MQTT 连接超时",
        aliases=("mqtt", "broker", "连接超时", "TLS", "三元组"),
        required_fields=("device_model", "network_type", "mqtt_connected", "error_code"),
        follow_up_questions={
            "device_model": TroubleshootingQuestion(
                field="device_model",
                question="请确认设备型号，例如 GW-100、GW-200、GW-500。",
                options=["GW-100", "GW-200", "GW-500", "其他"],
            ),
            "network_type": TroubleshootingQuestion(
                field="network_type",
                question="当前网络接入方式是什么？",
                options=["4G", "以太网", "Wi-Fi", "不确定"],
            ),
            "mqtt_connected": TroubleshootingQuestion(
                field="mqtt_connected",
                question="后台显示 MQTT 是否已连接？",
                options=["是", "否", "不确定"],
            ),
            "error_code": TroubleshootingQuestion(
                field="error_code",
                question="是否有 MQTT 或认证相关错误码？没有则填“无”。",
                options=["E101", "E102", "E104", "无"],
            ),
        },
        default_action="核对 Broker 地址、端口、TLS 证书、设备三元组、防火墙策略和弱网重连日志。",
    ),
    TroubleshootingTree(
        issue_type="固件升级失败",
        aliases=("升级", "固件", "版本", "回滚", "ota"),
        required_fields=("device_model", "last_upgrade_status", "error_code", "network_type"),
        follow_up_questions={
            "device_model": TroubleshootingQuestion(
                field="device_model",
                question="请确认升级失败的设备型号。",
                options=["GW-100", "GW-200", "TH-30", "其他"],
            ),
            "last_upgrade_status": TroubleshootingQuestion(
                field="last_upgrade_status",
                question="最近一次升级状态是什么？",
                options=["failed", "running", "idle", "不确定"],
            ),
            "error_code": TroubleshootingQuestion(
                field="error_code",
                question="升级失败时是否有错误码？没有则填“无”。",
                options=["E201", "E203", "E206", "无"],
            ),
            "network_type": TroubleshootingQuestion(
                field="network_type",
                question="升级时设备使用的网络接入方式是什么？",
                options=["4G", "以太网", "Wi-Fi", "不确定"],
            ),
        },
        default_action="先收集升级日志，确认固件包型号匹配、电量充足、网络稳定，人工复核前避免反复升级。",
    ),
)

HIGH_RISK_WORDS = (
    "冒烟",
    "烧毁",
    "赔偿",
    "投诉",
    "安全事故",
    "数据丢失",
    "漏电",
    "起火",
    "法律责任",
    "责任结论",
    "X999",
)


def guide_troubleshooting(payload: TroubleshootingRequest) -> TroubleshootingResult:
    tree = _select_tree(payload)
    missing_fields = _missing_fields(tree, payload)
    risk_signal = _risk_signal(payload)
    collected_facts = _collected_facts(payload)

    if missing_fields:
        questions = [tree.follow_up_questions[field] for field in missing_fields[:3]]
        route = Route.review if risk_signal else Route.direct_answer
        priority = Priority.p1 if risk_signal else Priority.p3
        confidence = _confidence(payload, tree, missing_fields)
        action = "信息还不完整，先追问关键字段，再进入知识库检索或规则诊断。"
        return TroubleshootingResult(
            issue_type=tree.issue_type,
            route=route,
            priority=priority,
            confidence_score=confidence,
            missing_fields=missing_fields,
            follow_up_questions=questions,
            collected_facts=collected_facts,
            suggested_action=action,
            ticket_payload=_ticket_payload(payload, tree, priority, action) if risk_signal else None,
        )

    priority = _priority(payload, tree, risk_signal)
    route = _route(priority, payload)
    action = _action(payload, tree, route)
    return TroubleshootingResult(
        issue_type=tree.issue_type,
        route=route,
        priority=priority,
        confidence_score=_confidence(payload, tree, missing_fields),
        missing_fields=[],
        follow_up_questions=[],
        collected_facts=collected_facts,
        suggested_action=action,
        ticket_payload=_ticket_payload(payload, tree, priority, action) if route in {Route.review, Route.handoff} else None,
    )


def _select_tree(payload: TroubleshootingRequest) -> TroubleshootingTree:
    text = f"{payload.issue_type or ''} {payload.question}".lower()
    for tree in TREES:
        if tree.issue_type == payload.issue_type:
            return tree
        if any(alias.lower() in text for alias in tree.aliases):
            return tree
    return TREES[0]


def _missing_fields(tree: TroubleshootingTree, payload: TroubleshootingRequest) -> list[str]:
    missing = []
    for field in tree.required_fields:
        value = getattr(payload, field)
        if value is None or value == "":
            missing.append(field)
    return missing


def _risk_signal(payload: TroubleshootingRequest) -> str | None:
    if payload.risk_signal:
        return payload.risk_signal
    for word in HIGH_RISK_WORDS:
        if word in payload.question:
            return word
    return None


def _priority(payload: TroubleshootingRequest, tree: TroubleshootingTree, risk_signal: str | None) -> Priority:
    if risk_signal:
        return Priority.p1
    if tree.issue_type == "固件升级失败" and payload.last_upgrade_status == "failed":
        return Priority.p1
    if payload.online_status == "离线" or payload.mqtt_connected is False:
        return Priority.p2
    if payload.error_code and payload.error_code != "无":
        return Priority.p2
    return Priority.p3


def _route(priority: Priority, payload: TroubleshootingRequest) -> Route:
    if priority == Priority.p1:
        return Route.handoff
    if priority == Priority.p2 or len(payload.tried_steps) >= 2:
        return Route.review
    return Route.direct_answer


def _action(payload: TroubleshootingRequest, tree: TroubleshootingTree, route: Route) -> str:
    prefix = tree.default_action
    if route == Route.handoff:
        return f"{prefix} 当前问题风险较高，建议转人工并保留设备日志、现场照片和最近 30 分钟平台记录。"
    if route == Route.review:
        return f"{prefix} 如按上述步骤仍未恢复，建议人工复核。"
    return prefix


def _confidence(payload: TroubleshootingRequest, tree: TroubleshootingTree, missing_fields: list[str]) -> float:
    supplied = len(tree.required_fields) - len(missing_fields)
    score = 0.45 + supplied * 0.1
    if payload.error_code and payload.error_code != "无":
        score += 0.08
    if not missing_fields:
        score += 0.12
    return min(0.95, round(score, 2))


def _collected_facts(payload: TroubleshootingRequest) -> dict[str, str]:
    fields = (
        "issue_type",
        "device_model",
        "error_code",
        "online_status",
        "indicator_light",
        "network_type",
        "heartbeat_age_sec",
        "mqtt_connected",
        "last_upgrade_status",
        "risk_signal",
    )
    facts: dict[str, str] = {}
    for field in fields:
        value = getattr(payload, field)
        if value is not None and value != "":
            facts[field] = str(value)
    return facts


def _ticket_payload(
    payload: TroubleshootingRequest,
    tree: TroubleshootingTree,
    priority: Priority,
    action: str,
) -> TicketCreate:
    summary = (
        f"{payload.device_model or '未知型号'} 触发{tree.issue_type}排障；"
        f"错误码={payload.error_code or '未知'}，网络={payload.network_type or '未知'}，"
        f"已尝试操作={'; '.join(payload.tried_steps) if payload.tried_steps else '未提供'}。"
    )
    return TicketCreate(
        question=payload.question,
        device_model=payload.device_model,
        error_code=None if payload.error_code == "无" else payload.error_code,
        category=tree.issue_type,
        priority=priority,
        summary=summary,
        retrieved_sources=["troubleshooting_tree"],
        suggested_action=action,
    )
