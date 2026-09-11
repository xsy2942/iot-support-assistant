from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ticket_service.models import AgentRequest
from ticket_service.react_agent import ReActSupportAgent

DEFAULT_QUESTIONS = ROOT / "eval" / "questions.csv"
DEFAULT_CHALLENGE_QUESTIONS = ROOT / "eval" / "challenge_questions.csv"
DEFAULT_REPORT = ROOT / "reports" / "agent_eval_report.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def normalize_route(route: str) -> str:
    if route == "rag_answer":
        return "direct_answer"
    return route


def evaluate(questions_path: Path, top_k: int, challenge_path: Path | None = DEFAULT_CHALLENGE_QUESTIONS) -> dict[str, object]:
    agent = ReActSupportAgent()
    questions = [{**item, "dataset": "generated"} for item in read_csv(questions_path)]
    if challenge_path and challenge_path.exists():
        questions.extend({**item, "dataset": "challenge"} for item in read_csv(challenge_path))
    cases = []
    route_correct = 0
    citation_count = 0
    complete_or_partial = 0
    evidence_quality_hits = 0
    evidence_quality_total = 0

    for item in questions:
        response = agent.respond(AgentRequest(question=item["question"], top_k=top_k))
        actual_route = normalize_route(response.route.value)
        route_hit = actual_route == item["expected_route"]
        has_citation = bool(response.evidence) and item["expected_route"] == "direct_answer"
        expected_hint = item["expected_doc_hint"]
        evidence_text = "\n".join(
            f"{evidence.title} {evidence.quote} {evidence.metadata.get('error_code', '')}" for evidence in response.evidence
        )
        top3_hit = item["expected_route"] != "direct_answer" or expected_hint in evidence_text
        expected_model = item.get("expected_device_model", "")
        expected_code = item.get("expected_error_code", "")
        expected_pairs = [
            (expected_model, expected_code)
            for evidence in response.evidence[:top_k]
            if evidence.metadata.get("device_model") == expected_model or evidence.metadata.get("error_code") == expected_code
        ]
        needs_strict_evidence = item["expected_route"] == "direct_answer" and bool(expected_model or expected_code)
        if needs_strict_evidence:
            evidence_quality_total += 1
            if expected_pairs:
                evidence_quality_hits += 1

        route_correct += int(route_hit)
        citation_count += int(has_citation)
        complete_or_partial += int(response.status.value in {"COMPLETE", "PARTIAL"})
        cases.append(
            {
                "question_id": item["question_id"],
                "dataset": item["dataset"],
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
                "strict_evidence_match": bool(expected_pairs) if needs_strict_evidence else None,
                "difficulty": item.get("difficulty", ""),
            }
        )

    total = len(questions)
    direct_total = sum(1 for item in cases if item["expected_route"] == "direct_answer")
    handoff_total = sum(1 for item in cases if item["expected_route"] == "handoff")
    clarify_total = sum(1 for item in cases if item["expected_route"] == "clarify")
    report = {
        "total_questions": total,
        "top_k": top_k,
        "dataset_counts": _group_counts(cases, "dataset"),
        "route_accuracy": round(route_correct / total, 4),
        "citation_coverage": round(citation_count / direct_total, 4) if direct_total else 0.0,
        "top3_recall": round(sum(1 for item in cases if item["top3_hit"]) / total, 4),
        "strict_evidence_match_rate": round(evidence_quality_hits / evidence_quality_total, 4) if evidence_quality_total else 0.0,
        "handoff_accuracy": round(
            sum(1 for item in cases if item["expected_route"] == "handoff" and item["route_correct"])
            / max(1, handoff_total),
            4,
        ),
        "clarify_accuracy": round(
            sum(1 for item in cases if item["expected_route"] == "clarify" and item["route_correct"])
            / max(1, clarify_total),
            4,
        ),
        "completion_rate": round(complete_or_partial / total, 4),
        "by_dataset": _group_metrics(cases, "dataset"),
        "by_difficulty": _group_metrics(cases, "difficulty"),
        "cases": cases,
    }
    return report


def _group_counts(cases: list[dict[str, object]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in cases:
        group = str(item.get(key) or "unknown")
        counts[group] = counts.get(group, 0) + 1
    return counts


def _group_metrics(cases: list[dict[str, object]], key: str) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for item in cases:
        group = str(item.get(key) or "unknown")
        groups.setdefault(group, []).append(item)
    return {
        group: {
            "count": len(items),
            "route_accuracy": round(sum(1 for item in items if item["route_correct"]) / len(items), 4),
            "top3_recall": round(sum(1 for item in items if item["top3_hit"]) / len(items), 4),
        }
        for group, items in sorted(groups.items())
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--challenge-questions", type=Path, default=DEFAULT_CHALLENGE_QUESTIONS)
    parser.add_argument("--no-challenge", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    report = evaluate(args.questions, args.top_k, None if args.no_challenge else args.challenge_questions)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
