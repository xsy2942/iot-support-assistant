# IoT Support Agent

IoT 设备售后智能体与工单闭环系统。

这是一个面向 IoT 设备售后场景的个人项目，重点覆盖设备离线、MQTT 连接超时、网关心跳丢失、固件升级失败、传感器采样异常、温湿度/振动/电压异常等问题。项目主链路是 Python 自研 ReAct Agent：根据每轮 Observation 动态选择 memory.read、troubleshooting.guide、knowledge.search、ticket.draft、final.answer 等工具，最后做证据校验与转人工判断。

## 当前进度

已完成：

- 500 条 IoT 售后知识分块：FAQ、错误码说明、历史工单、产品手册。
- 150 条生成问答评测集、40 条挑战评测集与本地 RAG / Agent 评测。
- 120 条遥测样例与 80 条诊断评测脚本。
- Python ReAct Agent 编排接口：Reason -> Action -> Observation -> Verify 动态执行链。
- 本地混合检索：基于 `knowledge_chunks.csv` 做中文字符 n-gram 向量检索 + 关键词召回 + 设备型号/错误码/问题类型业务重排，并支持父子块聚合去重。
- Agent 会话记忆：通过 `session_id` 合并多轮设备型号、错误码、网络状态等上下文字段，Redis 可选持久化短期记忆。
- MCP Server：基于官方 `mcp` Python SDK 暴露 `agent_respond`、`knowledge_search`、`ticket_create` 工具，并提供知识库资源与 Prompt 模板。
- SSE 流式输出：提供 `GET /agent/respond/stream`，前端可逐步接收路由、规划、检索和最终结果事件。
- FastAPI 工单服务：创建工单、查看工单、更新状态、记录反馈、输出评测报告。
- 中文客服工作台：支持客户原话、排障字段、待处理工单续办、折叠式设备状态诊断和图片附件入口，优先展示建议回复、参考依据、工单号和今日处理统计。
- 图片能力边界：当前版本保存图片附件元数据并随工单流转，不做自动视觉识别；如需识别设备面板或错误截图，可继续接 OCR 或多模态模型。
- 轻量多轮排障：用户描述不完整时先追问设备型号、错误码、在线状态、网络类型等关键信息。
- DeepSeek、阿里云百炼、Tavily 接入检查脚本。

## 技术栈

- Python 3 + FastAPI + Uvicorn + Pydantic
- MCP Python SDK
- PostgreSQL 工单存储，SQLite 仅作为本地测试兜底
- Redis 可选保存多轮排障短期上下文
- HTML / CSS / JavaScript 中文前端
- CSV / Markdown 领域数据集
- scikit-learn 本地 TF-IDF 混合检索与 baseline 评测
- DeepSeek / 百炼 OpenAI-compatible API
- Tavily Web Search API

## 本地启动

```powershell
.\.venv\Scripts\python.exe -m uvicorn ticket_service.main:app --reload --host 127.0.0.1 --port 8000
```

如需使用 PostgreSQL 作为工单数据库，在 `.env` 中配置：

```text
TICKET_DB_URL=postgresql://postgres:postgres@localhost:5432/iot_support_assistant
```

如需保存多轮排障上下文，在 `.env` 中配置：

```text
TROUBLESHOOTING_REDIS_URL=redis://localhost:6379/0
TROUBLESHOOTING_SESSION_TTL_SECONDS=172800
AGENT_MEMORY_REDIS_URL=redis://localhost:6379/0
AGENT_MEMORY_TTL_SECONDS=172800
```

连接检查：

```powershell
.\.venv\Scripts\python.exe scripts\check_postgres.py
.\.venv\Scripts\python.exe scripts\check_redis.py
```

打开：

- 项目前端：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

多轮排障接口：

- `POST /agent/respond`：Python Agent 主入口，负责路由、规划、知识库检索、排障追问、转人工草稿和证据校验
- `GET /agent/respond/stream`：SSE 流式 Agent 响应，返回 `step` 和 `result` 事件
- `GET /agent/memory/{session_id}`：查看某个 Agent 会话记忆
- `DELETE /agent/memory/{session_id}`：清空某个 Agent 会话记忆
- `POST /troubleshooting/next`：根据已知信息生成下一步追问或处理建议
- `POST /troubleshooting/create-ticket`：高风险或建议复核时创建工单

独立 MCP Server：

```powershell
.\.venv\Scripts\python.exe -m ticket_service.mcp_server --transport stdio
.\.venv\Scripts\python.exe -m ticket_service.mcp_server --transport streamable-http --host 127.0.0.1 --port 8010 --path /mcp
```

## 数据生成

```powershell
.\.venv\Scripts\python.exe scripts\generate_iot_data.py
.\.venv\Scripts\python.exe scripts\generate_telemetry_data.py
```

主要输出：

- `data/raw/faq.csv`
- `data/raw/error_codes.csv`
- `data/raw/historical_tickets.csv`
- `data/raw/manuals/*.md`
- `data/raw/telemetry_samples.csv`
- `data/processed/knowledge_chunks.csv`
- `eval/questions.csv`
- `eval/diagnostic_cases.csv`

## 本地评测

```powershell
.\.venv\Scripts\python.exe eval\run_eval.py
.\.venv\Scripts\python.exe eval\run_agent_eval.py
.\.venv\Scripts\python.exe eval\run_diagnostic_eval.py
```

报告输出：

- `reports/eval_report.json`
- `reports/agent_eval_report.json`
- `reports/diagnostic_eval_report.json`

当前评测分成两层：生成集用于验证链路可复现，挑战集用于检查口语改写、信息缺失、未知错误码和高风险转人工边界。不要把生成集 100% 写成真实泛化能力，简历更建议写合并挑战集后的指标。

当前本地结果：

- 生成问答集：150 条，Top3 召回率 100%，路由准确率 100%。
- 合并挑战集：190 条，Top3 召回率 97.89%，路由准确率 95.79%，严格证据匹配率 83.33%，转人工准确率 92.31%，追问准确率 72.73%。
- 诊断评测集：80 条，分类、优先级、路由准确率 100%。

## Agent 主链路

当前项目不把模型输出直接当作任务完成，而是把一次用户请求交给 ReAct-style 执行器动态选择工具：

1. `Reason`：基于当前问题、会话记忆和上一轮 Observation 判断下一步。
2. `Action`：动态选择 `memory.read`、`troubleshooting.guide`、`knowledge.search`、`ticket.draft`、`final.answer` 等工具。
3. `Observation`：记录工具返回的缺失字段、召回证据、风险信号或工单草稿。
4. `Verify`：检查是否有引用证据、是否命中高风险词、最终状态是 `COMPLETE / PARTIAL / UNKNOWN / INCOMPLETE`。

Agent 记忆策略：

- 请求携带 `session_id` 时，系统会合并历史上下文字段。
- 默认使用进程内 memory，适合本地演示。
- 配置 `AGENT_MEMORY_REDIS_URL` 后，使用 Redis 保存短期会话记忆和最近 20 轮对话摘要，默认保留 2 天，便于跨天继续处理同一个工单。
- 可以通过 `GET /agent/memory/{session_id}` 查看上下文字段和历史轮次。
- 可以通过 `DELETE /agent/memory/{session_id}` 清空会话。

MCP Server 工具：

- `agent_respond`：执行 Agent 主链路
- `knowledge_search`：检索本地 IoT 知识库
- `ticket_create`：创建转人工工单
- `iot://knowledge/summary`：知识库统计资源
- `iot_support_prompt`：IoT 售后支持 Prompt 模板

示例：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/agent/respond -ContentType "application/json" -Body '{
  "question": "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？",
  "device_model": "GW-200",
  "error_code": "E104",
  "online_status": "离线",
  "network_type": "4G",
  "mqtt_connected": false,
  "heartbeat_age_sec": 900
}'
```

更多说明见：

- [docs/setup.md](docs/setup.md)
- [docs/agent_architecture.md](docs/agent_architecture.md)
- [docs/evaluation_methodology.md](docs/evaluation_methodology.md)
- [docs/model_config.md](docs/model_config.md)
- [docs/postgresql.md](docs/postgresql.md)
- [docs/diagnostics.md](docs/diagnostics.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [docs/project_positioning.md](docs/project_positioning.md)
