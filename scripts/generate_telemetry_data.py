from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from random import Random


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
EVAL_DIR = ROOT / "eval"


DEVICES = [
    ("DEV-GW200-001", "gateway", "GW-200", "v2.0.1"),
    ("DEV-GW500-002", "gateway", "GW-500", "v2.3.0"),
    ("DEV-TH030-003", "sensor", "TH-30", "v1.4.3"),
    ("DEV-AQ020-004", "sensor", "AQ-20", "v1.2.0"),
    ("DEV-VB300-005", "vibration", "VB-300", "v2.0.1"),
    ("DEV-PM200-006", "power_meter", "PM-200", "v2.3.0"),
]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_samples() -> list[dict[str, object]]:
    rng = Random(20260401)
    base = datetime(2026, 4, 1, 9, 0, 0)
    samples: list[dict[str, object]] = []
    patterns = ["normal", "offline", "mqtt_timeout", "upgrade_failed", "sensor_drift", "voltage_risk", "safety"]

    for index in range(1, 81):
        device_id, product_line, model, firmware = DEVICES[index % len(DEVICES)]
        pattern = patterns[index % len(patterns)]
        sample = {
            "sample_id": f"TEL-{index:03d}",
            "timestamp": (base + timedelta(minutes=index * 12)).isoformat(),
            "device_id": device_id,
            "product_line": product_line,
            "device_model": model,
            "firmware_version": firmware,
            "online": True,
            "mqtt_connected": True,
            "heartbeat_age_sec": rng.randint(5, 70),
            "rssi_dbm": rng.randint(-78, -48),
            "battery_percent": rng.randint(45, 96),
            "temperature_c": round(rng.uniform(19, 32), 1),
            "humidity_percent": round(rng.uniform(35, 70), 1),
            "vibration_mm_s": round(rng.uniform(0.2, 3.2), 2),
            "voltage_v": round(rng.uniform(218, 232), 1),
            "error_code": "",
            "last_upgrade_status": "idle",
            "customer_risk_signal": "",
            "expected_category": "normal",
            "expected_priority": "P3",
            "expected_route": "direct_answer",
        }

        if pattern == "offline":
            sample.update(
                {
                    "online": False,
                    "mqtt_connected": False,
                    "heartbeat_age_sec": rng.randint(600, 2400),
                    "rssi_dbm": rng.randint(-108, -92),
                    "error_code": "E104",
                    "expected_category": "device_offline",
                    "expected_priority": "P1",
                    "expected_route": "handoff",
                }
            )
        elif pattern == "mqtt_timeout":
            sample.update(
                {
                    "mqtt_connected": False,
                    "heartbeat_age_sec": rng.randint(180, 520),
                    "rssi_dbm": rng.randint(-95, -82),
                    "error_code": "E102",
                    "expected_category": "mqtt_timeout",
                    "expected_priority": "P2",
                    "expected_route": "review",
                }
            )
        elif pattern == "upgrade_failed":
            sample.update(
                {
                    "last_upgrade_status": "failed",
                    "battery_percent": rng.randint(8, 18),
                    "error_code": "E203",
                    "expected_category": "firmware_upgrade_failed",
                    "expected_priority": "P1",
                    "expected_route": "handoff",
                }
            )
        elif pattern == "sensor_drift":
            sample.update(
                {
                    "temperature_c": round(rng.uniform(58, 72), 1),
                    "humidity_percent": round(rng.uniform(88, 96), 1),
                    "error_code": "E302",
                    "expected_category": "sensor_sampling_abnormal",
                    "expected_priority": "P2",
                    "expected_route": "review",
                }
            )
        elif pattern == "voltage_risk":
            sample.update(
                {
                    "voltage_v": round(rng.uniform(252, 268), 1),
                    "error_code": "E304",
                    "expected_category": "power_sampling_risk",
                    "expected_priority": "P1",
                    "expected_route": "handoff",
                }
            )
        elif pattern == "safety":
            sample.update(
                {
                    "online": False,
                    "mqtt_connected": False,
                    "heartbeat_age_sec": rng.randint(300, 1800),
                    "error_code": "E206",
                    "customer_risk_signal": "smoke_or_short_circuit",
                    "expected_category": "safety_risk",
                    "expected_priority": "P1",
                    "expected_route": "handoff",
                }
            )
        samples.append(sample)
    return samples


def build_cases(samples: list[dict[str, object]]) -> list[dict[str, object]]:
    cases = []
    for sample in samples[:40]:
        cases.append(
            {
                "case_id": sample["sample_id"].replace("TEL", "DIA"),
                "sample_id": sample["sample_id"],
                "expected_category": sample["expected_category"],
                "expected_priority": sample["expected_priority"],
                "expected_route": sample["expected_route"],
            }
        )
    return cases


def main() -> None:
    samples = build_samples()
    cases = build_cases(samples)
    write_csv(RAW_DIR / "telemetry_samples.csv", samples)
    write_csv(EVAL_DIR / "diagnostic_cases.csv", cases)
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "telemetry_sample_count": len(samples),
        "diagnostic_case_count": len(cases),
    }
    (DATA_DIR / "telemetry_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
