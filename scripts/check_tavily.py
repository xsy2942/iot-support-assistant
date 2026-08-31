from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    api_key = os.getenv("TAVILY_API_KEY")
    base_url = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

    if not api_key:
        raise SystemExit("TAVILY_API_KEY is missing. Put it in .env first.")

    response = httpx.post(
        f"{base_url.rstrip('/')}/search",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "query": "IoT MQTT heartbeat timeout troubleshooting",
            "search_depth": "basic",
            "max_results": 2,
            "include_answer": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    print(
        {
            "status": "ok",
            "result_count": len(data.get("results", [])),
            "first_result": (data.get("results") or [{}])[0].get("title"),
        }
    )


if __name__ == "__main__":
    main()
