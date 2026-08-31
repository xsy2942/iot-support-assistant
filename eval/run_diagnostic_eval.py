from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ticket_service.diagnostics import analyze_telemetry
from ticket_service.models import TelemetrySample

DEFAULT_SAMPLES = ROOT / "data" / "raw" / "telemetry_samples.csv"
DEFAULT_CASES = ROOT / "eval" / "diagnostic_cases.csv"
DEFAULT_REPORT = ROOT / "reports" / "diagnostic_eval_report.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_sample(row: dict[str, str]) -> TelemetrySample:
    adapter = TypeAdapter(TelemetrySample)
    typed = {
        **row,
        "online": row["online"].lower() == "true",
        "mqtt_connected": row["mqtt_connected"].lower() == "true",
        "heartbeat_age_sec": int(row["heartbeat_age_sec"]),
        "rssi_dbm": int(row["rssi_dbm"]),
        "battery_percent": int(row["battery_percent"]),
        "temperature_c": float(row["temperature_c"]),
        "humidity_percent": float(row["humidity_percent"]),
        "vibration_mm_s": float(row["vibration_mm_s"]),
        "voltage_v": float(row["voltage_v"]),
        "error_code": row.get("error_code") or None,
        "customer_risk_signal": row.get("customer_risk_signal") or None,
    }
    return adapter.validate_python(typed)


def evaluate(samples_path: Path, cases_path: Path) -> dict[str, object]:
    samples = {row["sample_id"]: load_sample(row) for row in read_csv(samples_path)}
    cases = read_csv(cases_path)
    results = []
    category_hits = 0
    priority_hits = 0
    route_hits = 0

    for case in cases:
        result = analyze_telemetry(samples[case["sample_id"]])
        category_hit = result.category == case["expected_category"]
        priority_hit = result.priority.value == case["expected_priority"]
        route_hit = result.route.value == case["expected_route"]
        category_hits += int(category_hit)
        priority_hits += int(priority_hit)
        route_hits += int(route_hit)
        results.append(
            {
                "case_id": case["case_id"],
                "sample_id": case["sample_id"],
                "expected_category": case["expected_category"],
                "actual_category": result.category,
                "expected_priority": case["expected_priority"],
                "actual_priority": result.priority.value,
                "expected_route": case["expected_route"],
                "actual_route": result.route.value,
                "category_hit": category_hit,
                "priority_hit": priority_hit,
                "route_hit": route_hit,
            }
        )

    total = len(cases)
    return {
        "total_cases": total,
        "category_accuracy": round(category_hits / total, 4),
        "priority_accuracy": round(priority_hits / total, 4),
        "route_accuracy": round(route_hits / total, 4),
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    report = evaluate(args.samples, args.cases)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
