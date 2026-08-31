# Telemetry Diagnostics

遥测诊断层用于增强项目的 IoT 属性，让它不只是一个通用客服问答系统。

## 数据

生成脚本：

```powershell
.\.venv\Scripts\python.exe scripts\generate_telemetry_data.py
```

输出：

- `data/raw/telemetry_samples.csv`
- `eval/diagnostic_cases.csv`
- `data/telemetry_manifest.json`

核心字段：

- `online`
- `mqtt_connected`
- `heartbeat_age_sec`
- `rssi_dbm`
- `battery_percent`
- `temperature_c`
- `humidity_percent`
- `vibration_mm_s`
- `voltage_v`
- `error_code`
- `last_upgrade_status`
- `customer_risk_signal`

## 诊断规则

规则实现位于：

```text
ticket_service/diagnostics.py
```

当前支持：

- `device_offline`
- `mqtt_timeout`
- `firmware_upgrade_failed`
- `sensor_sampling_abnormal`
- `power_sampling_risk`
- `safety_risk`
- `weak_signal`
- `normal`

诊断结果包含：

- 故障分类
- 优先级 P1/P2/P3
- 路由策略：直接回答、建议复核、转人工
- 置信度
- 证据与建议动作
- 可选工单 payload

## API

```text
POST /diagnostics/analyze
POST /diagnostics/create-ticket
```

`/diagnostics/analyze` 返回诊断结果，不创建工单。

`/diagnostics/create-ticket` 会在需要复核或转人工时自动创建工单。

## 评测

```powershell
.\.venv\Scripts\python.exe eval\run_diagnostic_eval.py
```

输出：

```text
reports/diagnostic_eval_report.json
```
