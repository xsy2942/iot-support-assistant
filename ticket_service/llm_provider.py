from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class AgentModelSettings:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float = 45.0
    max_tokens: int = 900
    max_retries: int = 1
    temperature: float = 0.1

    @classmethod
    def from_env(cls, provider: str | None = None) -> "AgentModelSettings":
        selected = (provider or os.getenv("AGENT_PROVIDER", "deepseek")).strip().lower()
        if selected == "deepseek":
            prefix = "DEEPSEEK"
            default_base_url = "https://api.deepseek.com"
            default_model = "deepseek-chat"
        elif selected in {"bailian", "dashscope", "qwen"}:
            selected = "bailian"
            prefix = "BAILIAN"
            default_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            default_model = "qwen-plus"
        else:
            raise ValueError(f"Unsupported AGENT_PROVIDER: {selected}")

        return cls(
            provider=selected,
            api_key=os.getenv(f"{prefix}_API_KEY", "").strip(),
            base_url=os.getenv(f"{prefix}_BASE_URL", default_base_url).strip(),
            model=os.getenv(f"{prefix}_MODEL", default_model).strip(),
            timeout_seconds=float(os.getenv("AGENT_MODEL_TIMEOUT_SECONDS", "45")),
            max_tokens=int(os.getenv("AGENT_MODEL_MAX_TOKENS", "900")),
            max_retries=int(os.getenv("AGENT_MODEL_MAX_RETRIES", "1")),
            temperature=float(os.getenv("AGENT_MODEL_TEMPERATURE", "0.1")),
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


class OpenAIChatToolModel:
    """Small adapter for OpenAI-compatible chat-completions tool calling."""

    def __init__(self, settings: AgentModelSettings, client: Any | None = None) -> None:
        if not settings.configured and client is None:
            raise ValueError(f"{settings.provider} API key is not configured")
        self.settings = settings
        self.client = client or OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        return self.client.chat.completions.create(
            model=self.settings.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )
