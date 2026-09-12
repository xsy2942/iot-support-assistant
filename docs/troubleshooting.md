# Troubleshooting Guide

本模块用于处理“用户描述不完整”的 IoT 售后问题。它不是完整客服会话系统，而是一个轻量级多轮排障入口：先识别问题类型，再检查缺失字段，最后决定追问、建议复核或转人工建单。

## 覆盖范围

当前先覆盖 3 类高频问题：

- 设备离线
- MQTT 连接超时
- 固件升级失败

这样做是为了保证演示和面试表达足够清晰，避免一次性覆盖过多 IoT 故障类型。

## 流程

```text
用户模糊描述
  ↓
识别故障类型
  ↓
检查关键信息是否缺失
  ↓
缺信息：返回 1-3 个追问问题
信息足够：输出建议动作和处理路由
风险较高：生成工单草稿
```

## 关键信息

不同故障类型需要不同字段。

设备离线：

- 设备型号
- 在线状态
- 指示灯状态
- 网络类型
- 错误码

MQTT 连接超时：

- 设备型号
- 网络类型
- MQTT 连接状态
- 错误码

固件升级失败：

- 设备型号
- 最近升级状态
- 错误码
- 网络类型

## API

生成下一步追问或处理建议：

```text
POST /troubleshooting/next
```

基于排障结果创建工单：

```text
POST /troubleshooting/create-ticket
```

示例请求：

```json
{
  "session_id": null,
  "question": "设备连不上平台了，现场人员也说不清楚具体原因。",
  "issue_type": "设备离线",
  "device_model": null,
  "error_code": null,
  "online_status": null,
  "indicator_light": null,
  "network_type": null,
  "heartbeat_age_sec": null,
  "mqtt_connected": null,
  "last_upgrade_status": null,
  "tried_steps": [],
  "risk_signal": null
}
```

示例响应会返回：

- `missing_fields`：缺失的字段
- `follow_up_questions`：建议追问的问题
- `session_id`：启用 Redis 后用于继续同一轮排障
- `route`：直接回答、建议复核或转人工
- `ticket_payload`：需要建单时的工单草稿

## Redis 会话记忆

默认情况下，排障接口仍然可以无状态运行：前端或调用方每次把已收集的信息带给接口，后端返回下一步结果。

如果配置 Redis，系统会启用轻量会话记忆：

- 使用 `session_id` 区分用户会话
- 把已收集字段作为 JSON 快照存入 Redis
- 设置 TTL，自动清理过期排障会话
- 每次用户补充信息后更新 Redis，再调用排障规则

在 `.env` 中配置：

```text
TROUBLESHOOTING_REDIS_URL=redis://localhost:6379/0
TROUBLESHOOTING_SESSION_TTL_SECONDS=172800
```

检查 Redis 连接：

```powershell
.\.venv\Scripts\python.exe scripts\check_redis.py
```

配置后，第一次调用 `/troubleshooting/next` 可以不传 `session_id`，服务会生成一个新的 `session_id`。后续调用带上这个 `session_id`，系统会把之前已经收集过的设备型号、错误码、在线状态、网络类型等字段合并进当前请求。

这属于“短期上下文记忆”，适合客服排障过程。长期数据仍然保存到 PostgreSQL。
