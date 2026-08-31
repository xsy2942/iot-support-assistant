from __future__ import annotations

import argparse
import json

from ask_rag import DEFAULT_QUESTION, answer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--web", action="store_true", help="Include Tavily web search results.")
    args = parser.parse_args()
    print(json.dumps(answer(args.question, "deepseek", args.top_k, args.web), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
