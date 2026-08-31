from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EVAL_DIR = ROOT / "eval"


PRODUCT_LINES = {
    "工业网关": ["GW-100", "GW-200", "GW-500"],
    "环境传感器": ["TH-10", "TH-30", "AQ-20"],
    "振动监测": ["VB-100", "VB-300"],
    "电力采集": ["PM-80", "PM-200"],
}

ISSUES = [
    ("设备离线", "检查供电、网络、SIM 卡余额、MQTT Broker 地址和最近心跳时间"),
    ("MQTT 连接超时", "核对 Broker 域名、端口、TLS 证书、设备三元组和防火墙策略"),
    ("固件升级失败", "确认固件包型号匹配、电量充足、升级窗口稳定且断点续传可用"),
    ("传感器采样异常", "检查采样周期、探头接线、量程配置、校准系数和环境干扰"),
    ("网关心跳丢失", "查看心跳间隔、NTP 时间、弱网重连日志和平台接入状态"),
    ("设备绑定失败", "确认 SN/IMEI 未被占用、租户信息正确、二维码未过期"),
    ("电压数据异常", "核对互感器方向、倍率参数、接线相序和采样通道"),
    ("温度数据漂移", "检查安装位置、校准日期、补偿参数和传感器老化情况"),
    ("振动阈值误报", "检查安装底座、阈值模板、采样频率和设备工况变化"),
    ("平台告警延迟", "检查上报频率、消息队列积压、规则引擎状态和网络延迟"),
]

ERRORS = [
    ("E101", "设备认证失败", "设备三元组错误或密钥被重置", "高"),
    ("E102", "MQTT Broker 不可达", "Broker 地址、端口或 DNS 解析异常", "中"),
    ("E103", "TLS 握手失败", "证书过期、系统时间错误或协议版本不匹配", "高"),
    ("E104", "心跳超时", "弱网、SIM 卡欠费、网关掉电或防火墙拦截", "中"),
    ("E105", "设备重复绑定", "SN/IMEI 已绑定到其他租户或历史项目", "中"),
    ("E106", "NTP 同步失败", "NTP 服务器不可达或本地网络限制 UDP 123", "低"),
    ("E107", "配置下发失败", "设备离线、配置版本冲突或参数校验未通过", "中"),
    ("E108", "网关存储空间不足", "日志文件过大或缓存消息未及时清理", "中"),
    ("E109", "蜂窝网络注册失败", "SIM 卡停机、APN 错误或基站信号弱", "高"),
    ("E110", "以太网链路断开", "网线、交换机端口或静态 IP 配置异常", "中"),
    ("E201", "固件包校验失败", "固件包损坏、签名错误或型号不匹配", "高"),
    ("E202", "升级电量不足", "电池设备低于升级安全阈值", "中"),
    ("E203", "升级过程断连", "网络不稳定或设备重启导致下载中断", "高"),
    ("E204", "版本回退受限", "目标版本低于最小兼容版本", "中"),
    ("E205", "升级后配置迁移失败", "旧版本配置字段缺失或格式不兼容", "高"),
    ("E206", "Bootloader 启动失败", "升级包损坏或存储分区异常", "高"),
    ("E207", "灰度策略未命中", "设备不在灰度批次或标签条件不匹配", "低"),
    ("E208", "固件下载超时", "下载源慢、网络丢包或代理配置错误", "中"),
    ("E301", "温度探头断路", "探头接线松动或传感器损坏", "中"),
    ("E302", "湿度读数越界", "探头进水、校准系数错误或量程设置异常", "中"),
    ("E303", "振动采样溢出", "冲击过大、量程过低或采样芯片异常", "高"),
    ("E304", "电压相序错误", "三相接线顺序错误或互感器方向反接", "高"),
    ("E305", "采样周期非法", "平台下发周期低于设备支持下限", "低"),
    ("E306", "校准参数缺失", "设备恢复出厂后未重新写入校准表", "中"),
    ("E307", "传感器总线冲突", "RS485 地址重复或终端电阻配置错误", "中"),
    ("E308", "电流通道无数据", "互感器未接入、通道关闭或倍率为 0", "中"),
    ("E401", "告警规则执行失败", "规则表达式错误或字段名不存在", "中"),
    ("E402", "消息队列积压", "上报峰值过高或消费服务异常", "高"),
    ("E403", "数据写入超时", "时序库压力过大或索引写入阻塞", "高"),
    ("E404", "设备影子版本冲突", "多端同时修改配置导致版本号不一致", "中"),
]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_faq() -> list[dict[str, object]]:
    rows = []
    faq_id = 1
    firmware_versions = ["v1.2.0", "v1.4.3", "v2.0.1", "v2.3.0"]
    for product_line, models in PRODUCT_LINES.items():
        for model in models:
            for issue, steps in ISSUES[:5]:
                if faq_id > 40:
                    return rows
                rows.append(
                    {
                        "doc_id": f"FAQ-{faq_id:03d}",
                        "product_line": product_line,
                        "device_model": model,
                        "firmware_version": firmware_versions[faq_id % len(firmware_versions)],
                        "issue_type": issue,
                        "error_code": ERRORS[faq_id % len(ERRORS)][0],
                        "risk_level": "高" if issue in {"固件升级失败", "设备离线"} else "中",
                        "source_type": "FAQ",
                        "question": f"{model} 出现{issue}时应该怎么排查？",
                        "answer": f"针对 {model} 的{issue}，建议先{steps}。若 10 分钟内无法恢复，保留设备日志并转交二线支持。",
                        "standard_steps": steps,
                    }
                )
                faq_id += 1
    return rows


def build_error_codes() -> list[dict[str, object]]:
    rows = []
    models = [model for values in PRODUCT_LINES.values() for model in values]
    for index, (code, title, cause, risk) in enumerate(ERRORS, start=1):
        model = models[index % len(models)]
        rows.append(
            {
                "doc_id": f"ERR-{index:03d}",
                "error_code": code,
                "title": title,
                "product_line": next(line for line, values in PRODUCT_LINES.items() if model in values),
                "device_model": model,
                "firmware_version": ["v1.2.0", "v1.4.3", "v2.0.1", "v2.3.0"][index % 4],
                "issue_type": title,
                "risk_level": risk,
                "possible_reason": cause,
                "standard_steps": f"定位 {code} 时，先确认现场现象，再检查配置、网络与设备日志；若风险等级为高，需要生成工单并附上最近 30 分钟日志。",
                "source_type": "错误码说明",
            }
        )
    return rows


def build_tickets() -> list[dict[str, object]]:
    rows = []
    models = [model for values in PRODUCT_LINES.values() for model in values]
    base_time = datetime(2026, 4, 1, 9, 0, 0)
    for i in range(1, 51):
        model = models[i % len(models)]
        issue, steps = ISSUES[i % len(ISSUES)]
        error_code = ERRORS[(i * 3) % len(ERRORS)][0]
        priority = "P1" if issue in {"设备离线", "固件升级失败"} else ("P2" if i % 3 else "P3")
        status = "已解决" if i % 5 else "已转人工"
        rows.append(
            {
                "ticket_id": f"TCK-2026-{i:04d}",
                "product_line": next(line for line, values in PRODUCT_LINES.items() if model in values),
                "device_model": model,
                "firmware_version": ["v1.2.0", "v1.4.3", "v2.0.1", "v2.3.0"][i % 4],
                "issue_type": issue,
                "error_code": error_code,
                "priority": priority,
                "risk_level": "高" if priority == "P1" else "中",
                "question": f"客户反馈 {model} {issue}，平台记录错误码 {error_code}，现场已尝试重启但未完全恢复。",
                "resolution": f"工程师按标准流程{steps}，并核对日志中的 {error_code} 记录。处理后观察两个心跳周期，数据恢复正常。",
                "suggested_action": "直接指导客户排查" if status == "已解决" else "建议转人工并收集日志",
                "status": status,
                "created_at": (base_time + timedelta(hours=i * 7)).isoformat(),
                "source_type": "历史工单",
            }
        )
    return rows


def build_manuals() -> list[dict[str, object]]:
    manuals = []
    manual_specs = [
        ("MAN-001", "GW-200 快速运维手册", "GW-200", "工业网关", ["设备上线", "MQTT 配置", "心跳诊断", "日志导出"]),
        ("MAN-002", "TH-30 环境传感器安装手册", "TH-30", "环境传感器", ["安装位置", "温湿度校准", "采样周期", "异常读数"]),
        ("MAN-003", "VB-300 振动监测调试手册", "VB-300", "振动监测", ["安装底座", "采样频率", "阈值模板", "误报告警"]),
        ("MAN-004", "PM-200 电力采集排障手册", "PM-200", "电力采集", ["相序检查", "倍率设置", "电压电流采样", "告警规则"]),
    ]
    for doc_id, title, model, line, chapters in manual_specs:
        content = [
            f"# {title}",
            "",
            f"适用产品线：{line}",
            f"适用设备型号：{model}",
            "适用固件版本：v1.2.0 及以上",
            "",
        ]
        for chapter in chapters:
            content.extend(
                [
                    f"## {chapter}",
                    f"{model} 在处理{chapter}相关问题时，应先确认设备状态、现场接线、平台配置和最近日志。",
                    "若问题涉及安全风险、客户投诉、数据丢失或远程操作失败，应停止强行给出结论并生成工单交由人工复核。",
                    "",
                ]
            )
        manuals.append(
            {
                "doc_id": doc_id,
                "title": title,
                "product_line": line,
                "device_model": model,
                "firmware_version": "v1.2.0+",
                "source_type": "产品手册",
                "content": "\n".join(content),
            }
        )
    return manuals


def build_eval_questions() -> list[dict[str, object]]:
    rows = []
    models = [model for values in PRODUCT_LINES.values() for model in values]
    for i in range(1, 43):
        model = models[i % len(models)]
        issue, _ = ISSUES[i % len(ISSUES)]
        rows.append(
            {
                "question_id": f"Q-{i:03d}",
                "question": f"{model} 出现{issue}，应该先检查哪些项目？",
                "expected_route": "direct_answer",
                "expected_doc_hint": issue,
                "category": issue,
                "difficulty": "single_doc",
            }
        )
    for i in range(43, 55):
        model = models[i % len(models)]
        code, title, *_ = ERRORS[i % len(ERRORS)]
        rows.append(
            {
                "question_id": f"Q-{i:03d}",
                "question": f"{model} 报 {code}，同时平台有{title}和心跳异常，需要怎么综合判断？",
                "expected_route": "direct_answer",
                "expected_doc_hint": code,
                "category": "多文档组合",
                "difficulty": "multi_doc",
            }
        )
    handoff_questions = [
        "客户要求赔偿停机损失，但知识库里没有合同赔偿条款，应该怎么答？",
        "设备现场疑似短路冒烟，客户要求远程继续升级固件，应该怎么处理？",
        "客户说历史数据全部丢失，需要确认法律责任，知识库没有相关说明。",
        "出现错误码 X999，资料库没有这个错误码，能不能直接告诉客户原因？",
        "客户投诉多次维修未解决，要求升级负责人介入。",
        "设备涉及人身安全事故，客户要求立即给出责任结论。",
    ]
    for offset, question in enumerate(handoff_questions, start=55):
        rows.append(
            {
                "question_id": f"Q-{offset:03d}",
                "question": question,
                "expected_route": "handoff",
                "expected_doc_hint": "转人工",
                "category": "转人工",
                "difficulty": "out_of_scope",
            }
        )
    return rows


def build_knowledge_chunks(
    faq: list[dict[str, object]],
    errors: list[dict[str, object]],
    tickets: list[dict[str, object]],
    manuals: list[dict[str, object]],
) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    for row in faq:
        chunks.append(
            {
                "chunk_id": row["doc_id"],
                "source_type": row["source_type"],
                "title": row["question"],
                "product_line": row["product_line"],
                "device_model": row["device_model"],
                "error_code": row["error_code"],
                "issue_type": row["issue_type"],
                "content": f"{row['question']}\n{row['answer']}\n标准步骤：{row['standard_steps']}",
            }
        )
    for row in errors:
        chunks.append(
            {
                "chunk_id": row["doc_id"],
                "source_type": row["source_type"],
                "title": f"{row['error_code']} {row['title']}",
                "product_line": row["product_line"],
                "device_model": row["device_model"],
                "error_code": row["error_code"],
                "issue_type": row["issue_type"],
                "content": f"错误码 {row['error_code']}：{row['title']}。可能原因：{row['possible_reason']}。处理步骤：{row['standard_steps']}",
            }
        )
    for row in tickets:
        chunks.append(
            {
                "chunk_id": row["ticket_id"],
                "source_type": row["source_type"],
                "title": f"{row['device_model']} {row['issue_type']} 历史工单",
                "product_line": row["product_line"],
                "device_model": row["device_model"],
                "error_code": row["error_code"],
                "issue_type": row["issue_type"],
                "content": f"{row['question']}\n解决方案：{row['resolution']}\n建议动作：{row['suggested_action']}",
            }
        )
    for row in manuals:
        chunks.append(
            {
                "chunk_id": row["doc_id"],
                "source_type": row["source_type"],
                "title": row["title"],
                "product_line": row["product_line"],
                "device_model": row["device_model"],
                "error_code": "",
                "issue_type": "产品手册",
                "content": row["content"],
            }
        )
    return chunks


def main() -> None:
    faq = build_faq()
    errors = build_error_codes()
    tickets = build_tickets()
    manuals = build_manuals()
    eval_questions = build_eval_questions()
    chunks = build_knowledge_chunks(faq, errors, tickets, manuals)

    write_csv(RAW_DIR / "faq.csv", faq)
    write_csv(RAW_DIR / "error_codes.csv", errors)
    write_csv(RAW_DIR / "historical_tickets.csv", tickets)
    write_csv(EVAL_DIR / "questions.csv", eval_questions)
    write_csv(PROCESSED_DIR / "knowledge_chunks.csv", chunks)

    (RAW_DIR / "manuals").mkdir(parents=True, exist_ok=True)
    for manual in manuals:
        (RAW_DIR / "manuals" / f"{manual['doc_id']}.md").write_text(manual["content"], encoding="utf-8")

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "faq_count": len(faq),
        "error_code_count": len(errors),
        "historical_ticket_count": len(tickets),
        "manual_count": len(manuals),
        "eval_question_count": len(eval_questions),
        "knowledge_chunk_count": len(chunks),
    }
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
