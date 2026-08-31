from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    load_dotenv()
    api_key = os.getenv("BAILIAN_API_KEY")
    base_url = os.getenv("BAILIAN_BASE_URL")
    model = os.getenv("BAILIAN_MODEL", "qwen-plus")

    if not api_key:
        raise SystemExit("BAILIAN_API_KEY is missing. Put it in .env first.")
    if not base_url:
        raise SystemExit("BAILIAN_BASE_URL is missing. Put it in .env first.")

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个接口连通性检查助手，只回复 JSON。"},
            {"role": "user", "content": "回复 {\"status\":\"ok\"}"},
        ],
        temperature=0,
        max_tokens=32,
    )
    content = response.choices[0].message.content or ""
    if not content.strip():
        raise SystemExit("Bailian responded, but the message content was empty. Check BAILIAN_MODEL.")
    print(content)


if __name__ == "__main__":
    main()
