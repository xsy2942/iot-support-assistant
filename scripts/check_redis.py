from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    redis_url = os.getenv("TROUBLESHOOTING_REDIS_URL")
    if not redis_url:
        raise SystemExit("TROUBLESHOOTING_REDIS_URL is empty. Fill it in .env to enable Redis session memory.")

    try:
        import redis
    except ImportError as exc:
        raise SystemExit("redis is missing. Run: pip install -r requirements.txt") from exc

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    pong = client.ping()
    print(f"redis_ping={pong}")
    print("session_memory=redis")


if __name__ == "__main__":
    main()
