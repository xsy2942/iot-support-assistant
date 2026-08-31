from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWLEDGE_PATH = ROOT / "data" / "processed" / "knowledge_chunks.csv"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_fastgpt_token() -> str:
    token = os.getenv("FASTGPT_TOKEN", "").strip()
    if token:
        return token

    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "fastgpt-redis",
                "redis-cli",
                "-a",
                "mypassword",
                "--no-auth-warning",
                "keys",
                "fastgpt:session:*",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "未找到 FastGPT 登录态。请先打开 http://localhost:3000 登录一次，"
            "或手动设置 FASTGPT_TOKEN。"
        ) from exc

    keys = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not keys:
        raise RuntimeError("Redis 中没有 FastGPT session，请先在浏览器登录 FastGPT。")
    return keys[0].replace("fastgpt:session:", "", 1)


class FastGPTClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"token": token},
            timeout=120,
            trust_env=False,
        )

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        response = self.client.post(path, json=payload)
        return self._parse(response)

    def _parse(self, response: httpx.Response) -> Any:
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"FastGPT 返回了非 JSON 响应：{response.text[:500]}") from exc

        if response.status_code >= 400 or body.get("code") not in (None, 200):
            message = body.get("message") or body.get("statusText") or response.text[:500]
            raise RuntimeError(f"FastGPT API 调用失败：HTTP {response.status_code}, {message}")
        return body.get("data")


def read_chunks(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"知识分块文件不存在：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def find_dataset(client: FastGPTClient, name: str) -> str | None:
    datasets = client.post(
        "/api/core/dataset/list",
        {"parentId": None, "type": "dataset", "searchKey": name},
    )
    for item in datasets or []:
        if item.get("name") == name:
            return item.get("_id") or item.get("id")
    return None


def create_dataset(client: FastGPTClient, name: str, intro: str) -> str:
    data = client.post(
        "/api/core/dataset/create",
        {
            "parentId": None,
            "type": "dataset",
            "name": name,
            "intro": intro,
            "avatar": "core/dataset/commonDatasetColor",
            "vectorModel": "text-embedding-v4",
            "agentModel": "deepseek-chat",
        },
    )
    return str(data)


def create_collection(client: FastGPTClient, dataset_id: str, name: str) -> str:
    data = client.post(
        "/api/core/dataset/collection/create",
        {
            "datasetId": dataset_id,
            "parentId": None,
            "name": name,
            "type": "virtual",
            "tags": ["iot-support", "售后", "知识分块"],
        },
    )
    return str(data)


def find_collection(client: FastGPTClient, dataset_id: str, name: str) -> str | None:
    data = client.post(
        "/api/core/dataset/collection/list",
        {
            "pageNum": 1,
            "pageSize": 20,
            "datasetId": dataset_id,
            "parentId": None,
            "searchText": name,
            "selectFolder": False,
            "filterTags": [],
            "simple": True,
        },
    )
    for item in (data or {}).get("data", []):
        if item.get("name") == name:
            return item.get("_id") or item.get("id")
    return None


def build_fastgpt_rows(chunks: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in chunks:
        title = chunk["title"].strip()
        content = chunk["content"].strip()
        metadata = {
            "chunk_id": chunk["chunk_id"],
            "source_type": chunk["source_type"],
            "product_line": chunk["product_line"],
            "device_model": chunk["device_model"],
            "error_code": chunk["error_code"],
            "issue_type": chunk["issue_type"],
        }
        rows.append(
            {
                "q": title,
                "a": (
                    f"{content}\n\n"
                    f"来源：{metadata['source_type']} / {metadata['chunk_id']}；"
                    f"设备型号：{metadata['device_model']}；"
                    f"错误码：{metadata['error_code']}；"
                    f"问题类型：{metadata['issue_type']}"
                ),
                "indexes": [
                    {
                        "type": "custom",
                        "text": " ".join(
                            part
                            for part in [
                                title,
                                chunk["device_model"],
                                chunk["error_code"],
                                chunk["issue_type"],
                                chunk["product_line"],
                            ]
                            if part
                        ),
                    }
                ],
                "metadata": metadata,
            }
        )
    return rows


def push_rows(client: FastGPTClient, collection_id: str, rows: list[dict[str, Any]]) -> int:
    data = client.post(
        "/api/core/dataset/data/pushData",
        {
            "collectionId": collection_id,
            "data": rows,
            "trainingType": "chunk",
            "autoIndexes": False,
            "imageIndex": False,
            "indexSize": 512,
        },
    )
    return int((data or {}).get("insertLen", 0))


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 IoT 售后知识分块到 FastGPT。")
    parser.add_argument("--base-url", default=os.getenv("FASTGPT_BASE_URL", "http://localhost:3000"))
    parser.add_argument("--dataset-name", default="IoT 设备售后知识库")
    parser.add_argument("--collection-name", default="IoT 售后知识分块")
    parser.add_argument("--knowledge-path", type=Path, default=DEFAULT_KNOWLEDGE_PATH)
    parser.add_argument("--append", action="store_true", help="向已有同名集合追加数据。")
    parser.add_argument("--new-collection", action="store_true", help="不复用同名集合，强制新建集合。")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    token = get_fastgpt_token()
    client = FastGPTClient(args.base_url, token)
    chunks = read_chunks(args.knowledge_path)

    dataset_id = find_dataset(client, args.dataset_name)
    if dataset_id:
        print(f"复用已有知识库：{args.dataset_name} ({dataset_id})")
    else:
        dataset_id = create_dataset(
            client,
            args.dataset_name,
            "面向工业网关、传感器、边缘采集终端的售后问答、错误码排查和工单分流知识库。",
        )
        print(f"已创建知识库：{args.dataset_name} ({dataset_id})")

    collection_id = None if args.new_collection else find_collection(client, dataset_id, args.collection_name)
    if collection_id and not args.append:
        print(f"复用已有集合：{args.collection_name} ({collection_id})")
        print("已跳过重复导入；如需追加数据，请加 --append；如需新建集合，请加 --new-collection。")
        return 0
    if collection_id:
        print(f"复用已有集合并追加数据：{args.collection_name} ({collection_id})")
    else:
        collection_id = create_collection(client, dataset_id, args.collection_name)
        print(f"已创建集合：{args.collection_name} ({collection_id})")
    rows = build_fastgpt_rows(chunks)
    inserted = push_rows(client, collection_id, rows)
    print(f"已提交训练队列：{inserted}/{len(rows)} 条知识分块")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"导入失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
