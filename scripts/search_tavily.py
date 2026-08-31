from __future__ import annotations

import argparse
import json
import os

import httpx
from dotenv import load_dotenv


def search(query: str, max_results: int = 5) -> dict[str, object]:
    load_dotenv()
    api_key = os.getenv("TAVILY_API_KEY")
    base_url = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

    if not api_key:
        raise SystemExit("TAVILY_API_KEY is missing. Put it in .env first.")

    response = httpx.post(
        f"{base_url.rstrip('/')}/search",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": True,
            "include_raw_content": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="MQTT heartbeat timeout IoT gateway troubleshooting")
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(search(args.query, args.max_results), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
