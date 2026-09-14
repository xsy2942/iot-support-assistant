from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ticket_service.agent_factory import create_support_agent
from ticket_service.models import AgentRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LangGraph IoT support Agent with real LLM tool calling.")
    parser.add_argument("question")
    parser.add_argument("--provider", choices=["deepseek", "bailian"], default="deepseek")
    parser.add_argument("--session-id", default="cli-demo")
    parser.add_argument("--device-model")
    parser.add_argument("--error-code")
    parser.add_argument("--issue-type")
    parser.add_argument("--online-status")
    parser.add_argument("--network-type")
    parser.add_argument("--max-steps", type=int, default=6)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    agent = create_support_agent(mode="langgraph", provider=args.provider)
    response = agent.respond(
        AgentRequest(
            question=args.question,
            session_id=args.session_id,
            device_model=args.device_model,
            error_code=args.error_code,
            issue_type=args.issue_type,
            online_status=args.online_status,
            network_type=args.network_type,
            max_steps=args.max_steps,
        )
    )
    print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
