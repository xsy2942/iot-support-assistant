# IoT Support Assistant

IoT 设备技术支持知识库与工单助手。

这是一个面向 IoT 设备售后场景的个人项目，重点覆盖设备离线、MQTT 连接超时、网关心跳丢失、固件升级失败、传感器采样异常、温湿度/振动/电压异常等问题。当前主链路已经调整为 Python 自研轻量 Agent：先路由，再规划，再调用本地知识库检索、排障树和工单工具，最后做证据校验与转人工判断。FastGPT 只保留为可选外部平台对接，不再是项目主依赖。

## 当前进度

已完成：

- 124 条 IoT 售后知识分块：FAQ、错误码说明、历史工单、产品手册。
- 60 条问答评测集与本地 RAG sanity check。
- 40 条遥测诊断样例与诊断评测脚本。
- Python Agent 编排接口：Fast Router -> Structured Planner -> Knowledge Search -> Capability Executor -> Verifier。
- 本地混合检索：基于 `knowledge_chunks.csv` 做中文字符 n-gram 向量检索 + 设备型号/错误码关键词加权，并支持父子块聚合去重。
- Agent 会话记忆：通过 `session_id` 合并多轮设备型号、错误码、网络状态等上下文字段，Redis 可选持久化短期记忆。
- MCP 工具入口：提供 MCP-style JSON-RPC 的 `initialize`、`tools/list`、`tools/call`，把 Agent 回答、知识库检索和工单创建包装成工具。
- SSE 流式输出：提供 `GET /agent/respond/stream`，前端可逐步接收路由、规划、检索和最终结果事件。
- FastAPI 工单服务：创建工单、查看工单、更新状态、记录反馈、输出评测报告。
- 中文前端 Dashboard：设备诊断、转人工工单、反馈和指标展示。
- 轻量多轮排障：用户描述不完整时先追问设备型号、错误码、在线状态、网络类型等关键信息。
- DeepSeek、阿里云百炼、Tavily 接入检查脚本。
- FastGPT 独立 Docker runtime 可选保留，用于对照演示外部 RAG/Workflow 平台如何接入本项目工单服务。

## 技术栈

- Python 3 + FastAPI + Uvicorn + Pydantic
- PostgreSQL 工单存储，SQLite 仅作为本地测试兜底
- Redis 可选保存多轮排障短期上下文
- HTML / CSS / JavaScript 中文前端
- CSV / Markdown 领域数据集
- scikit-learn 本地 TF-IDF 混合检索与 baseline 评测
- DeepSeek / 百炼 OpenAI-compatible API
- Tavily Web Search API
- Docker Compose 可选运行 FastGPT、MongoDB、Redis、PostgreSQL/pgvector、MinIO、AIProxy

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
TROUBLESHOOTING_SESSION_TTL_SECONDS=1800
AGENT_MEMORY_REDIS_URL=redis://localhost:6379/0
AGENT_MEMORY_TTL_SECONDS=1800
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
- `POST /mcp`：MCP-style JSON-RPC 工具入口，支持工具发现与调用
- `POST /troubleshooting/next`：根据已知信息生成下一步追问或处理建议
- `POST /troubleshooting/create-ticket`：高风险或建议复核时创建工单

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

当前本地评测是模拟数据 sanity check，指标偏理想；最终简历数字建议以本地 Agent 跑完 60 条问答和 40 条诊断用例后的结果为准。

## Agent 主链路

当前项目不把模型输出直接当作任务完成，而是把一次用户请求拆成结构化执行链：

1. `Fast Router`：判断问题是信息不足、知识库可答、规则诊断还是需要转人工。
2. `Structured Planner`：生成可执行步骤，避免模型随意发挥。
3. `Knowledge Search`：在 `data/processed/knowledge_chunks.csv` 中做本地混合检索。
4. `Capability Executor`：调用知识库检索、轻量排障树和工单草稿工具。
5. `Verifier`：检查是否有引用证据、是否命中高风险词、最终状态是 `COMPLETE / PARTIAL / UNKNOWN / INCOMPLETE`。

Agent 记忆策略：

- 请求携带 `session_id` 时，系统会合并历史上下文字段。
- 默认使用进程内 memory，适合本地演示。
- 配置 `AGENT_MEMORY_REDIS_URL` 后，使用 Redis 保存短期会话记忆和最近 20 轮对话摘要。

MCP 工具调用示例：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/mcp -ContentType "application/json" -Body '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}'
```

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

## FastGPT 可选接入

FastGPT runtime 放在：

```text
D:\pycmexercise\fastgpt-runtime
```

本仓库不提交 FastGPT 源码。FastGPT 可以作为外部 RAG / Workflow 平台对照演示：

- Web 地址：[http://localhost:3000](http://localhost:3000)
- 知识库：`IoT 设备售后知识库`
- 知识集合：`IoT 售后知识分块`
- 导入数量：124 条
- 应用：`IoT Support Copilot`

重新导入知识库：

```powershell
.\.venv\Scripts\python.exe scripts\import_fastgpt_dataset.py
```

重新创建 FastGPT 应用：

```powershell
.\.venv\Scripts\python.exe scripts\create_fastgpt_app.py
```

演示 RAG 到工单闭环：

```powershell
.\.venv\Scripts\python.exe scripts\fastgpt_ticket_flow_demo.py "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？"
.\.venv\Scripts\python.exe scripts\fastgpt_ticket_flow_demo.py "客户要求赔偿停机损失，现场设备冒烟并且历史数据全部丢失，应该怎么答？"
```

更多说明见：

- [docs/setup.md](docs/setup.md)
- [docs/agent_architecture.md](docs/agent_architecture.md)
- [docs/model_config.md](docs/model_config.md)
- [docs/postgresql.md](docs/postgresql.md)
- [docs/docker_fastgpt_plan.md](docs/docker_fastgpt_plan.md)
- [docs/fastgpt_workflow.md](docs/fastgpt_workflow.md)
- [docs/diagnostics.md](docs/diagnostics.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [docs/project_positioning.md](docs/project_positioning.md)
