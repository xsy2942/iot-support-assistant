from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_PATH = ROOT / "data" / "processed" / "knowledge_chunks.csv"
RAG_PROMPT_PATH = ROOT / "prompts" / "rag_answer.md"
DEFAULT_QUESTION = "GW-200 reports E104 and heartbeat loss. How should we troubleshoot it?"


PROVIDERS = {
    "deepseek": {
        "api_key": "DEEPSEEK_API_KEY",
        "base_url": "DEEPSEEK_BASE_URL",
        "model": "DEEPSEEK_MODEL",
        "default_base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "bailian": {
        "api_key": "BAILIAN_API_KEY",
        "base_url": "BAILIAN_BASE_URL",
        "model": "BAILIAN_MODEL",
        "default_base_url": "",
        "default_model": "qwen-plus",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def retrieve(question: str, top_k: int) -> list[dict[str, str]]:
    docs = read_csv(KNOWLEDGE_PATH)
    corpus = [f"{doc['title']} {doc['content']} {doc['error_code']} {doc['issue_type']}" for doc in docs]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    doc_matrix = vectorizer.fit_transform(corpus)
    scores = cosine_similarity(vectorizer.transform([question]), doc_matrix).ravel()
    top_indices = scores.argsort()[::-1][:top_k]
    return [{**docs[index], "score": f"{float(scores[index]):.4f}"} for index in top_indices]


def build_context(sources: list[dict[str, str]]) -> str:
    blocks = []
    for source in sources:
        blocks.append(
            "\n".join(
                [
                    f"chunk_id: {source['chunk_id']}",
                    f"title: {source['title']}",
                    f"source_type: {source['source_type']}",
                    f"device_model: {source['device_model']}",
                    f"error_code: {source['error_code']}",
                    f"score: {source['score']}",
                    f"content: {source['content']}",
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def tavily_search(query: str, max_results: int = 3) -> list[dict[str, str]]:
    api_key = os.getenv("TAVILY_API_KEY")
    base_url = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")
    if not api_key:
        return []
    response = httpx.post(
        f"{base_url.rstrip('/')}/search",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        }
        for item in response.json().get("results", [])
    ]


def build_web_context(results: list[dict[str, str]]) -> str:
    blocks = []
    for index, result in enumerate(results, start=1):
        blocks.append(
            "\n".join(
                [
                    f"web_source: WEB-{index}",
                    f"title: {result['title']}",
                    f"url: {result['url']}",
                    f"content: {result['content']}",
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def get_client(provider: str) -> tuple[OpenAI, str]:
    config = PROVIDERS[provider]
    api_key = os.getenv(config["api_key"])
    base_url = os.getenv(config["base_url"], config["default_base_url"])
    model = os.getenv(config["model"], config["default_model"])
    if not api_key:
        raise SystemExit(f"{config['api_key']} is missing. Put it in .env first.")
    if not base_url:
        raise SystemExit(f"{config['base_url']} is missing. Put it in .env first.")
    return OpenAI(api_key=api_key, base_url=base_url), model


def answer(question: str, provider: str, top_k: int, use_web: bool = False) -> dict[str, object]:
    load_dotenv()
    sources = retrieve(question, top_k)
    web_results = tavily_search(question) if use_web else []
    system_prompt = RAG_PROMPT_PATH.read_text(encoding="utf-8")
    user_prompt = f"User question: {question}\n\nLocal knowledge base results:\n{build_context(sources)}"
    if web_results:
        user_prompt += f"\n\nTavily web search results:\n{build_web_context(web_results)}"
    client, model = get_client(provider)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=900,
    )
    return {
        "question": question,
        "provider": provider,
        "model": model,
        "sources": [
            {"chunk_id": source["chunk_id"], "title": source["title"], "score": source["score"]}
            for source in sources
        ],
        "web_sources": [{"title": result["title"], "url": result["url"]} for result in web_results],
        "answer": response.choices[0].message.content,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="deepseek")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--web", action="store_true", help="Include Tavily web search results.")
    args = parser.parse_args()
    print(json.dumps(answer(args.question, args.provider, args.top_k, args.web), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
