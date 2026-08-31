from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import httpx

from import_fastgpt_dataset import FastGPTClient, get_fastgpt_token, load_dotenv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_NAME = "IoT 设备售后知识库"
DEFAULT_TICKET_URL = "http://127.0.0.1:8000/tickets/create"

RISK_KEYWORDS = [
    "赔偿",
    "投诉",
    "法律责任",
    "责任结论",
    "人身安全",
    "安全事故",
    "冒烟",
    "短路",
    "数据全部丢失",
    "停机损失",
    "负责人介入",
]


def search_fastgpt(client: FastGPTClient, dataset_id: str, question: str) -> list[dict[str, Any]]:
    data = client.post(
        "/api/core/dataset/searchTest",
        {
            "datasetId": dataset_id,
            "text": question,
            "limit": 5000,
            "searchMode": "embedding",
            "similarity": 0.3,
            "usingReRank": False,
        },
    )
    return list((data or {}).get("list") or [])


def find_dataset(client: FastGPTClient, dataset_name: str) -> str:
    data = client.post(
        "/api/core/dataset/list",
        {"parentId": None, "type": "dataset", "searchKey": dataset_name},
    )
    for item in data or []:
        if item.get("name") == dataset_name:
            dataset_id = item.get("_id") or item.get("id")
            if dataset_id:
                return str(dataset_id)
    raise RuntimeError(f"未找到 FastGPT 知识库：{dataset_name}。请先运行 scripts/import_fastgpt_dataset.py。")


def top_score(hit: dict[str, Any]) -> float:
    scores = hit.get("score") or []
    if not scores:
        return 0.0
    return float(scores[0].get("value") or 0)


def extract_field(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def decide_route(question: str, hits: list[dict[str, Any]], threshold: float) -> tuple[str, str]:
    if any(keyword in question for keyword in RISK_KEYWORDS):
        return "handoff", "命中投诉、赔偿、安全或数据丢失等高风险关键词"
    if not hits:
        return "handoff", "FastGPT 知识库没有返回可用片段"
    score = top_score(hits[0])
    if score < threshold:
        return "handoff", f"最高相似度 {score:.3f} 低于阈值 {threshold:.2f}"
    error_code = extract_field(r"\b[A-Z]\d{3,4}\b", question)
    if error_code and not any(error_code in f"{hit.get('q', '')} {hit.get('a', '')}" for hit in hits[:3]):
        return "handoff", f"问题包含错误码 {error_code}，但 Top3 片段未覆盖"
    return "direct_answer", f"Top1 相似度 {score:.3f}，知识库片段可覆盖问题"


def build_answer(question: str, hits: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    sources = [
        {
            "title": hit.get("q", ""),
            "source": hit.get("sourceName", ""),
            "score": round(top_score(hit), 3),
        }
        for hit in hits[:3]
    ]
    return {
        "route": "direct_answer",
        "reason": reason,
        "question": question,
        "answer": hits[0].get("a", "") if hits else "",
        "sources": sources,
    }


def create_ticket(question: str, hits: list[dict[str, Any]], reason: str, ticket_url: str) -> dict[str, Any]:
    device_model = extract_field(r"\b[A-Z]{2,3}-\d{2,4}\b", question)
    error_code = extract_field(r"\b[A-Z]\d{3,4}\b", question)
    sources = [hit.get("q", "") for hit in hits[:3] if hit.get("q")]
    payload = {
        "question": question,
        "device_model": device_model,
        "firmware_version": None,
        "error_code": error_code,
        "category": "high_risk_or_low_confidence",
        "priority": "P1" if any(keyword in question for keyword in RISK_KEYWORDS) else "P2",
        "summary": f"{reason}。用户问题：{question[:80]}",
        "retrieved_sources": sources,
        "suggested_action": "建议人工复核：确认设备型号、固件版本、错误码、现场日志和客户风险诉求。",
    }
    response = httpx.post(ticket_url, json=payload, timeout=30, trust_env=False)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="演示 FastGPT 检索到本地工单服务的闭环。")
    parser.add_argument("question")
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--dataset-id")
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--ticket-url", default=DEFAULT_TICKET_URL)
    parser.add_argument("--threshold", type=float, default=0.62)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    fastgpt = FastGPTClient(args.base_url, get_fastgpt_token())
    dataset_id = args.dataset_id or find_dataset(fastgpt, args.dataset_name)
    hits = search_fastgpt(fastgpt, dataset_id, args.question)
    route, reason = decide_route(args.question, hits, args.threshold)

    if route == "handoff":
        result = {
            "route": route,
            "reason": reason,
            "top_sources": [hit.get("q", "") for hit in hits[:3]],
            "ticket": create_ticket(args.question, hits, reason, args.ticket_url),
        }
    else:
        result = build_answer(args.question, hits, reason)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
