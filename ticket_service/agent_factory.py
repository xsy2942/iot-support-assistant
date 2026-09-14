from __future__ import annotations

import os
from typing import Any

from .knowledge_base import KnowledgeBase
from .llm_provider import AgentModelSettings, OpenAIChatToolModel
from .react_agent import ReActSupportAgent


def create_support_agent(
    *,
    knowledge_base: KnowledgeBase | None = None,
    mode: str | None = None,
    provider: str | None = None,
    client: Any | None = None,
) -> Any:
    selected_mode = (mode or os.getenv("AGENT_MODE", "auto")).strip().lower()
    kb = knowledge_base or KnowledgeBase()
    if selected_mode == "deterministic":
        return ReActSupportAgent(kb)
    if selected_mode not in {"auto", "langgraph"}:
        raise ValueError("AGENT_MODE must be auto, langgraph, or deterministic")

    settings = AgentModelSettings.from_env(provider)
    if not settings.configured and client is None:
        if selected_mode == "langgraph":
            raise RuntimeError(f"AGENT_MODE=langgraph requires {settings.provider} API credentials")
        return ReActSupportAgent(kb)

    from .langgraph_agent import LangGraphSupportAgent

    model = OpenAIChatToolModel(settings, client=client)
    return LangGraphSupportAgent(model=model, knowledge_base=kb)
