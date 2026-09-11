from __future__ import annotations

import json
import time
from uuid import uuid4

from .models import AgentRequest, AgentResponse


FACT_FIELDS = (
    "issue_type",
    "device_model",
    "firmware_version",
    "error_code",
    "online_status",
    "indicator_light",
    "network_type",
    "heartbeat_age_sec",
    "mqtt_connected",
    "last_upgrade_status",
    "risk_signal",
)


class AgentMemoryStore:
    def __init__(self, redis_url: str | None = None, ttl_seconds: int = 1800, turn_limit: int = 20) -> None:
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.turn_limit = turn_limit
        self._client = None
        self._memory: dict[str, dict[str, object]] = {}
        if redis_url:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError("Redis agent memory backend requires redis. Run: pip install -r requirements.txt") from exc
            self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    @property
    def backend(self) -> str:
        return "redis" if self._client else "memory"

    def merge(self, payload: AgentRequest) -> AgentRequest:
        session_id = payload.session_id or f"ag-{uuid4().hex[:12]}"
        stored = self._load(session_id)
        stored_facts = stored.get("facts", {}) if stored else {}
        incoming = payload.model_dump(exclude_none=True)
        merged = {**stored_facts, **incoming, "session_id": session_id}
        return AgentRequest(**merged)

    def save_turn(self, request: AgentRequest, response: AgentResponse) -> None:
        if not request.session_id:
            return
        stored = self._load(request.session_id)
        facts = stored.get("facts", {}) if stored else {}
        facts.update(self._facts(request))
        turns = list(stored.get("turns", [])) if stored else []
        turns.append(
            {
                "question": request.question,
                "route": response.route.value,
                "status": response.status.value,
                "answer": response.answer[:500],
                "timestamp": int(time.time()),
            }
        )
        data = {
            "session_id": request.session_id,
            "facts": facts,
            "turns": turns[-self.turn_limit :],
            "updated_at": int(time.time()),
        }
        self._save(request.session_id, data)

    def facts(self, session_id: str | None) -> dict[str, str]:
        if not session_id:
            return {}
        stored = self._load(session_id)
        facts = stored.get("facts", {}) if stored else {}
        return {key: str(value) for key, value in facts.items() if value is not None and value != ""}

    def session(self, session_id: str) -> dict[str, object]:
        stored = self._load(session_id)
        return {
            "session_id": session_id,
            "backend": self.backend,
            "facts": stored.get("facts", {}) if stored else {},
            "turns": stored.get("turns", []) if stored else [],
            "updated_at": stored.get("updated_at") if stored else None,
            "ttl_seconds": self.ttl_seconds,
        }

    def clear(self, session_id: str) -> bool:
        if self._client:
            return bool(self._client.delete(self._key(session_id)))
        return self._memory.pop(session_id, None) is not None

    def _load(self, session_id: str) -> dict[str, object]:
        if self._client:
            raw = self._client.get(self._key(session_id))
            return json.loads(raw) if raw else {}
        return self._memory.get(session_id, {})

    def _save(self, session_id: str, data: dict[str, object]) -> None:
        if self._client:
            self._client.setex(self._key(session_id), self.ttl_seconds, json.dumps(data, ensure_ascii=False))
            return
        self._memory[session_id] = data

    @staticmethod
    def _facts(request: AgentRequest) -> dict[str, object]:
        facts = {}
        for field in FACT_FIELDS:
            value = getattr(request, field)
            if value is not None and value != "":
                facts[field] = value
        return facts

    @staticmethod
    def _key(session_id: str) -> str:
        return f"iot-support:agent-memory:{session_id}"
