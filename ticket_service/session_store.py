from __future__ import annotations

import json
from uuid import uuid4

from .models import TroubleshootingRequest


class TroubleshootingSessionStore:
    def __init__(self, redis_url: str | None = None, ttl_seconds: int = 172800) -> None:
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self._client = None
        if redis_url:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError("Redis session backend requires redis. Run: pip install -r requirements.txt") from exc
            self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    @property
    def backend(self) -> str:
        return "redis" if self._client else "stateless"

    def merge(self, payload: TroubleshootingRequest) -> TroubleshootingRequest:
        if self._client is None:
            return payload

        session_id = payload.session_id or f"ts-{uuid4().hex[:12]}"
        key = self._key(session_id)
        stored = self._load(key)
        incoming = payload.model_dump(exclude_none=True)
        merged = {**stored, **incoming, "session_id": session_id}
        self._save(key, merged)
        return TroubleshootingRequest(**merged)

    def save_result(self, payload: TroubleshootingRequest) -> None:
        if self._client is None or not payload.session_id:
            return
        self._save(self._key(payload.session_id), payload.model_dump(exclude_none=True))

    def _load(self, key: str) -> dict[str, object]:
        assert self._client is not None
        raw = self._client.get(key)
        if not raw:
            return {}
        return json.loads(raw)

    def _save(self, key: str, data: dict[str, object]) -> None:
        assert self._client is not None
        self._client.setex(key, self.ttl_seconds, json.dumps(data, ensure_ascii=False))

    @staticmethod
    def _key(session_id: str) -> str:
        return f"iot-support:troubleshooting:{session_id}"
