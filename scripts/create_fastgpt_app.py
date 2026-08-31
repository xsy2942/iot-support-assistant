from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from import_fastgpt_dataset import FastGPTClient, get_fastgpt_token, load_dotenv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_NAME = "IoT 设备售后知识库"


SYSTEM_PROMPT = """你是 IoT 设备技术支持助手，负责处理工业网关、传感器、边缘采集终端的售后问题。

回答规则：
1. 必须优先基于知识库检索片段回答，不要编造知识库之外的错误码、赔偿规则或安全结论。
2. 回答必须包含可执行排查步骤，并覆盖设备状态、网络配置、固件版本、错误码、最近日志和现场已尝试操作。
3. 如果资料不足、错误码不存在、客户涉及投诉/赔偿/安全事故/数据丢失，输出“建议转人工”，并生成工单摘要。
4. 结尾必须列出来源，格式为“来源：chunk_id / 标题”。

输出格式：
处理建议：
1. ...
2. ...
3. ...

需要客户补充：
- ...

来源：
- ...

是否转人工：是/否
"""


def create_rag_app(client: FastGPTClient, dataset_id: str, app_name: str) -> str:
    selected_dataset = {
        "datasetId": dataset_id,
        "avatar": "core/dataset/commonDatasetColor",
        "name": "IoT 设备售后知识库",
        "vectorModel": {"model": "text-embedding-v4"},
    }

    start_id = "workflowStartNodeId"
    dataset_node_id = "iotDatasetSearch"
    ai_node_id = "iotAnswerNode"

    modules: list[dict[str, Any]] = [
        {
            "nodeId": start_id,
            "name": "用户问题",
            "intro": "",
            "avatar": "core/workflow/template/workflowStart",
            "flowNodeType": "workflowStart",
            "position": {"x": 420, "y": 120},
            "version": "4.9.7",
            "inputs": [
                {
                    "key": "userChatInput",
                    "renderTypeList": ["reference", "textarea"],
                    "valueType": "string",
                    "label": "用户问题",
                    "toolDescription": "用户问题",
                    "required": True,
                }
            ],
            "outputs": [
                {
                    "id": "userChatInput",
                    "key": "userChatInput",
                    "label": "用户问题",
                    "type": "static",
                    "valueType": "string",
                },
                {
                    "id": "userFiles",
                    "key": "userFiles",
                    "label": "用户附件",
                    "type": "static",
                    "valueType": "arrayString",
                },
            ],
        },
        {
            "nodeId": dataset_node_id,
            "name": "IoT 知识库检索",
            "intro": "检索 IoT 售后知识、错误码和历史工单。",
            "avatar": "core/workflow/template/datasetSearch",
            "flowNodeType": "datasetSearchNode",
            "showStatus": True,
            "position": {"x": 760, "y": 120},
            "version": "4.9.2",
            "inputs": [
                {
                    "key": "datasets",
                    "renderTypeList": ["selectDataset", "reference"],
                    "label": "选择知识库",
                    "value": [selected_dataset],
                    "valueType": "selectDataset",
                    "list": [],
                    "required": True,
                },
                {
                    "key": "similarity",
                    "renderTypeList": ["selectDatasetParamsModal"],
                    "label": "",
                    "value": 0.35,
                    "valueType": "number",
                },
                {
                    "key": "limit",
                    "renderTypeList": ["hidden"],
                    "label": "",
                    "value": 5000,
                    "valueType": "number",
                },
                {
                    "key": "searchMode",
                    "renderTypeList": ["hidden"],
                    "label": "",
                    "value": "embedding",
                    "valueType": "string",
                },
                {
                    "key": "embeddingWeight",
                    "renderTypeList": ["hidden"],
                    "label": "",
                    "value": 0.7,
                    "valueType": "number",
                },
                {
                    "key": "usingReRank",
                    "renderTypeList": ["hidden"],
                    "label": "",
                    "value": False,
                    "valueType": "boolean",
                },
                {
                    "key": "datasetSearchUsingExtensionQuery",
                    "renderTypeList": ["hidden"],
                    "label": "",
                    "value": False,
                    "valueType": "boolean",
                },
                {
                    "key": "datasetSearchInput",
                    "renderTypeList": ["reference", "textarea"],
                    "label": "检索问题",
                    "value": [[start_id, "userChatInput"], [start_id, "userFiles"]],
                    "valueType": "arrayString",
                    "required": True,
                    "toolDescription": "要检索的用户问题",
                },
            ],
            "outputs": [
                {
                    "id": "quoteQA",
                    "key": "quoteQA",
                    "label": "知识库引用",
                    "type": "static",
                    "valueType": "datasetQuote",
                },
                {
                    "id": "system_error",
                    "key": "system_error",
                    "label": "异常信息",
                    "type": "error",
                    "valueType": "object",
                },
            ],
        },
        {
            "nodeId": ai_node_id,
            "name": "售后回答生成",
            "intro": "基于知识库引用生成排查建议。",
            "avatar": "core/workflow/template/aiChat",
            "flowNodeType": "chatNode",
            "showStatus": True,
            "position": {"x": 1110, "y": 120},
            "version": "4.9.7",
            "inputs": [
                {
                    "key": "model",
                    "renderTypeList": ["settingLLMModel", "reference"],
                    "label": "AI 模型",
                    "value": "deepseek-chat",
                    "valueType": "string",
                },
                {
                    "key": "temperature",
                    "renderTypeList": ["hidden"],
                    "label": "",
                    "value": 0.2,
                    "valueType": "number",
                },
                {
                    "key": "maxToken",
                    "renderTypeList": ["hidden"],
                    "label": "",
                    "value": 1800,
                    "valueType": "number",
                },
                {
                    "key": "isResponseAnswerText",
                    "renderTypeList": ["hidden"],
                    "label": "",
                    "value": True,
                    "valueType": "boolean",
                },
                {
                    "key": "aiChatQuoteRole",
                    "renderTypeList": ["hidden"],
                    "label": "",
                    "value": "system",
                    "valueType": "string",
                },
                {"key": "quoteTemplate", "renderTypeList": ["hidden"], "label": "", "valueType": "string"},
                {"key": "quotePrompt", "renderTypeList": ["hidden"], "label": "", "valueType": "string"},
                {
                    "key": "systemPrompt",
                    "renderTypeList": ["textarea", "reference"],
                    "label": "系统提示词",
                    "value": SYSTEM_PROMPT,
                    "valueType": "string",
                },
                {
                    "key": "history",
                    "renderTypeList": ["numberInput", "reference"],
                    "label": "聊天记录",
                    "required": True,
                    "min": 0,
                    "max": 30,
                    "value": 6,
                    "valueType": "chatHistory",
                },
                {
                    "key": "userChatInput",
                    "renderTypeList": ["reference", "textarea"],
                    "label": "用户问题",
                    "required": True,
                    "value": [start_id, "userChatInput"],
                    "valueType": "string",
                    "toolDescription": "用户问题",
                },
                {
                    "key": "quoteQA",
                    "renderTypeList": ["settingDatasetQuotePrompt"],
                    "label": "",
                    "debugLabel": "知识库引用",
                    "value": [dataset_node_id, "quoteQA"],
                    "valueType": "datasetQuote",
                },
                {
                    "key": "fileUrlList",
                    "renderTypeList": ["reference", "JSONEditor"],
                    "label": "用户附件",
                    "value": [[start_id, "userFiles"]],
                    "valueType": "arrayString",
                },
                {"key": "aiChatReasoning", "renderTypeList": ["hidden"], "label": "", "value": False, "valueType": "boolean"},
            ],
            "outputs": [
                {
                    "id": "history",
                    "key": "history",
                    "label": "新上下文",
                    "type": "static",
                    "valueType": "chatHistory",
                },
                {
                    "id": "answerText",
                    "key": "answerText",
                    "label": "AI 回复内容",
                    "type": "static",
                    "valueType": "string",
                },
            ],
        },
    ]

    edges = [
        {
            "source": start_id,
            "target": dataset_node_id,
            "sourceHandle": f"{start_id}-source-right",
            "targetHandle": f"{dataset_node_id}-target-left",
        },
        {
            "source": dataset_node_id,
            "target": ai_node_id,
            "sourceHandle": f"{dataset_node_id}-source-right",
            "targetHandle": f"{ai_node_id}-target-left",
        },
    ]

    data = client.post(
        "/api/core/app/create",
        {
            "parentId": None,
            "name": app_name,
            "avatar": "core/app/type/simpleFill",
            "intro": "IoT 售后知识问答、来源引用、低置信度转人工和工单闭环演示应用。",
            "type": "simple",
            "modules": modules,
            "edges": edges,
            "chatConfig": {
                "welcomeText": "你好，我是 IoT 售后助手。请描述设备型号、固件版本、错误码和现场现象。",
                "welcomeConfig": {
                    "welcomeText": "你好，我是 IoT 售后助手。请描述设备型号、固件版本、错误码和现场现象。"
                },
                "variables": [],
                "questionGuide": {"open": False},
                "ttsConfig": {"type": "web"},
                "whisperConfig": {"open": False, "autoSend": False, "autoTTSResponse": False},
            },
        },
    )
    return str(data)


def find_app(client: FastGPTClient, app_name: str) -> str | None:
    data = client.post(
        "/api/core/app/list",
        {"parentId": None, "searchKey": app_name},
    )
    for item in data or []:
        if item.get("name") == app_name:
            return item.get("_id") or item.get("id")
    return None


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


def main() -> int:
    parser = argparse.ArgumentParser(description="创建 IoT Support Copilot FastGPT 应用。")
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--dataset-id")
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--app-name", default="IoT Support Copilot")
    parser.add_argument("--force-new", action="store_true", help="强制新建同名应用。")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    client = FastGPTClient(args.base_url, get_fastgpt_token())
    if not args.force_new:
        existing_app_id = find_app(client, args.app_name)
        if existing_app_id:
            print(f"复用已有 FastGPT 应用：{args.app_name} ({existing_app_id})")
            return 0
    dataset_id = args.dataset_id or find_dataset(client, args.dataset_name)
    app_id = create_rag_app(client, dataset_id, args.app_name)
    print(f"已创建 FastGPT 应用：{args.app_name} ({app_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
