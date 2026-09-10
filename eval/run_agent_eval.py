from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ticket_service.agent import SupportAgent
from ticket_service.models import AgentRequest

DEFAULT_QUESTIONS = ROOT / "eval" / "questions.csv"
DEFAULT_REPORT = ROOT / "reports" / "agent_eval_report.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def normalize_route(route: str) -> str:
    if route == "rag_answer":
        return "direct_answer"
    if route == "clarify":
        return "direct_answer"
    return route


def evaluate(questions_path: Path, top_k: int) -> dict[str, object]:
    agent = SupportAgent()
    questions = read_csv(questions_path)
    cases = []
    route_correct = 0
    citation_count = 0
    complete_or_partial = 0

    for item in questions:
        response = agent.respond(AgentRequest(question=item["question"], top_k=top_k))
        actual_route = normalize_route(response.route.value)
        route_hit = actual_route == item["expected_route"]
        has_citation = bool(response.evidence) and actual_route == "direct_answer"
        expected_hint = item["expected_doc_hint"]
        evidence_text = "\n".join(
            f"{evidence.title} {evidence.quote} {evidence.metadata.get('error_code', '')}" for evidence in response.evidence
        )
        top3_hit = expected_hint == "转人工" or expected_hint in evidence_text

        route_correct += int(route_hit)
        citation_count += int(has_citation)
        complete_or_partial += int(response.status.value in {"COMPLETE", "PARTIAL"})
        cases.append(
            {
                "question_id": item["question_id"],
                "question": item["question"],
                "expected_route": item["expected_route"],
                "actual_agent_route": response.route.value,
                "normalized_route": actual_route,
                "status": response.status.value,
                "confidence_score": response.confidence_score,
                "top_sources": [evidence.source_id for evidence in response.evidence[:top_k]],
                "top3_hit": top3_hit,
                "route_correct": route_hit,
                "has_citation": has_citation,
            }
        )

    total = len(questions)
    direct_total = sum(1 for item in cases if item["normalized_route"] == "direct_answer")
    handoff_total = sum(1 for item in cases if item["expected_route"] == "handoff")
    report = {
        "total_questions": total,
        "top_k": top_k,
        "route_accuracy": round(route_correct / total, 4),
        "citation_coverage": round(citation_count / direct_total, 4) if direct_total else 0.0,
        "top3_recall": round(sum(1 for item in cases if item["top3_hit"]) / total, 4),
        "handoff_accuracy": round(
            sum(1 for item in cases if item["expected_route"] == "handoff" and item["route_correct"])
            / max(1, handoff_total),
            4,
        ),
        "completion_rate": round(complete_or_partial / total, 4),
        "cases": cases,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    report = evaluate(args.questions, args.top_k)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
