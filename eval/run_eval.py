from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWLEDGE = ROOT / "data" / "processed" / "knowledge_chunks.csv"
DEFAULT_QUESTIONS = ROOT / "eval" / "questions.csv"
DEFAULT_REPORT = ROOT / "reports" / "eval_report.json"

HANDOFF_KEYWORDS = ["赔偿", "投诉", "安全事故", "冒烟", "法律责任", "数据全部丢失", "X999", "责任结论"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def should_handoff(question: str, top_score: float, top_docs: list[dict[str, str]]) -> bool:
    if any(keyword in question for keyword in HANDOFF_KEYWORDS):
        return True
    if top_score < 0.08:
        return True
    error_codes = re.findall(r"\b[A-Z]\d{3}\b", question)
    known_codes = {doc["error_code"] for doc in top_docs if doc.get("error_code")}
    return bool(error_codes) and not any(code in known_codes for code in error_codes)


def evaluate(knowledge_path: Path, questions_path: Path, top_k: int) -> dict[str, object]:
    docs = read_csv(knowledge_path)
    questions = read_csv(questions_path)
    corpus = [f"{doc['title']} {doc['content']} {doc['error_code']} {doc['issue_type']}" for doc in docs]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    doc_matrix = vectorizer.fit_transform(corpus)

    cases = []
    hit_count = 0
    route_correct = 0
    citation_count = 0

    for item in questions:
        query_vector = vectorizer.transform([item["question"]])
        scores = cosine_similarity(query_vector, doc_matrix).ravel()
        top_indices = scores.argsort()[::-1][:top_k]
        top_docs = [docs[index] for index in top_indices]
        top_score = float(scores[top_indices[0]]) if len(top_indices) else 0.0
        expected_hint = item["expected_doc_hint"]
        retrieved_text = "\n".join(f"{doc['title']} {doc['content']} {doc['error_code']}" for doc in top_docs)
        retrieved_sources = [doc["chunk_id"] for doc in top_docs]
        hit = expected_hint == "转人工" or expected_hint in retrieved_text
        actual_route = "handoff" if should_handoff(item["question"], top_score, top_docs) else "direct_answer"
        route_hit = actual_route == item["expected_route"]
        has_citation = bool(retrieved_sources) and actual_route == "direct_answer"

        hit_count += int(hit)
        route_correct += int(route_hit)
        citation_count += int(has_citation)
        cases.append(
            {
                "question_id": item["question_id"],
                "question": item["question"],
                "expected_route": item["expected_route"],
                "actual_route": actual_route,
                "expected_doc_hint": expected_hint,
                "top_score": round(top_score, 4),
                "top_sources": retrieved_sources,
                "top3_hit": hit,
                "route_correct": route_hit,
                "has_citation": has_citation,
            }
        )

    total = len(questions)
    direct_total = sum(1 for item in cases if item["actual_route"] == "direct_answer")
    report = {
        "total_questions": total,
        "top_k": top_k,
        "top3_recall": round(hit_count / total, 4),
        "route_accuracy": round(route_correct / total, 4),
        "citation_coverage": round(citation_count / direct_total, 4) if direct_total else 0.0,
        "handoff_accuracy": round(
            sum(1 for item in cases if item["expected_route"] == "handoff" and item["route_correct"])
            / max(1, sum(1 for item in cases if item["expected_route"] == "handoff")),
            4,
        ),
        "cases": cases,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge", type=Path, default=DEFAULT_KNOWLEDGE)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    report = evaluate(args.knowledge, args.questions, args.top_k)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {key: value for key, value in report.items() if key != "cases"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
